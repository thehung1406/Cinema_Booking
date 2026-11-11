"""Aggregates are read from current rows, so retries and edits cannot double count."""
from datetime import timedelta, timezone
import hashlib
import json
from math import sqrt

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from .config import Settings
from .models import Review, ReviewSentiment, SentimentDecision, utcnow
from .events import changed



def locked_review(db, review_id):
    review = db.exec(select(Review).where(Review.id == review_id).with_for_update()).first()
    if review is None or review.is_deleted:
        raise HTTPException(404, "Đánh giá không tồn tại")
    return review


def invalidate(db, review):
    result = db.get(ReviewSentiment, review.id)
    if result is None:
        result = ReviewSentiment(review_id=review.id, content_version=review.content_version)
    result.analysis_generation = (result.analysis_generation or 0) + 1
    result.lease_token = result.lease_until = None
    result.content_version = review.content_version
    result.status = "pending"
    result.label = None
    result.scores = {}
    result.model_version = None
    result.predicted_label = None
    result.decision_source = None
    result.confirmed_by_user_id = None
    result.confirmed_at = None
    result.confirmation_note = None
    result.attempts = 0
    result.updated_at = utcnow()
    db.add(result)
    changed(db, review, result)


def create_review(db, film_id, user_id, content, settings):
    review = db.exec(select(Review).where(Review.user_id == user_id, Review.film_id == film_id).with_for_update()).first()
    if review and not review.is_deleted:
        raise HTTPException(409, "Bạn đã có đánh giá cho phim này; hãy chỉnh sửa đánh giá.")
    if review:
        review.content_version += 1
        review.content = content
        review.is_deleted = False
        review.updated_at = utcnow()
    else:
        review = Review(user_id=user_id, film_id=film_id, content=content, content_version=1, event_version=0, updated_at=utcnow(), is_deleted=False)
    review.moderation_status = "approved" if settings.auto_approve else "pending"
    db.add(review)
    try:
        db.flush()
        invalidate(db, review)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Tài khoản đã có đánh giá cho phim này")
    db.refresh(review)
    return review


def edit_review(db, review_id, user_id, body, settings):
    review = locked_review(db, review_id)
    if review.user_id != user_id:
        raise HTTPException(403, "Bạn chỉ được sửa đánh giá của mình")
    if review.content_version != body.content_version:
        raise HTTPException(409, "Đánh giá đã thay đổi. Vui lòng tải lại.")
    review.content = body.content
    review.content_version += 1
    review.updated_at = utcnow()
    review.moderation_status = "approved" if settings.auto_approve else "pending"
    invalidate(db, review)
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def delete_review(db, review_id, user_id):
    review = locked_review(db, review_id)
    if review.user_id != user_id:
        raise HTTPException(403, "Bạn chỉ được xóa đánh giá của mình")
    review.is_deleted = True
    review.content = ""  # Do not retain deleted user text.
    review.content_version += 1
    review.updated_at = utcnow()
    invalidate(db, review)
    db.add(review)
    db.commit()


def moderate_review(db, review_id, body):
    review = locked_review(db, review_id)
    if review.content_version != body.content_version:
        raise HTTPException(409, "Nội dung đã thay đổi; cần duyệt lại phiên bản mới")
    review.moderation_status = body.status
    invalidate(db, review)
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def sentiment_item(review, result):
    stamp = result.updated_at
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return dict(review_id=review.id, film_id=review.film_id, content=review.content,
                content_version=review.content_version, analysis_generation=result.analysis_generation,
                analysis_status=result.status, label=result.label, predicted_label=result.predicted_label,
                scores=result.scores, model_version=result.model_version, decision_source=result.decision_source,
                updated_at=stamp.isoformat())


def decide_sentiment(db, review_id, actor_user_id, body):
    """Lock review -> result, CAS, invalidate inference, audit+event in one commit."""
    digest = hashlib.sha256(json.dumps({"review_id": review_id, **body.model_dump(mode="json")},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    # Serialize repeated request IDs, including attempts against different reviews.
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,17))"),
                   {"key": f"{actor_user_id}:{body.request_id}"})
    replay = db.exec(select(SentimentDecision).where(SentimentDecision.actor_user_id == actor_user_id,
        SentimentDecision.request_id == str(body.request_id))).first()
    if replay:
        if replay.request_digest != digest:
            raise HTTPException(409, "Mã yêu cầu đã được dùng cho quyết định khác")
        return replay.response
    review = locked_review(db, review_id)
    result = db.get(ReviewSentiment, review_id, with_for_update=True)
    def utc(value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if (review.moderation_status != "approved" or not result or
            review.content_version != body.content_version or result.content_version != body.content_version or
            result.analysis_generation != body.analysis_generation or
            utc(result.updated_at) != utc(body.expected_updated_at) or
            result.status not in {"needs_review", "succeeded"}):
        raise HTTPException(409, "Kết quả đã thay đổi hoặc chưa thể xác nhận; tải lại danh sách")
    previous = result.label
    result.predicted_label = result.predicted_label or (result.label if result.decision_source != "staff" else None)
    result.label, result.status, result.decision_source = body.label, "succeeded", "staff"
    result.confirmed_by_user_id, result.confirmed_at = actor_user_id, utcnow()
    result.confirmation_note = body.reason
    result.analysis_generation += 1
    result.lease_token = result.lease_until = None
    result.updated_at = result.confirmed_at
    # Review.updated_at remains unchanged: confirming a label does not refresh the review window.
    changed(db, review, result, "ReviewSentimentUpdated.v1")
    response = {k: v for k, v in sentiment_item(review, result).items() if k != "content"}
    db.add(SentimentDecision(review_id=review_id, actor_user_id=actor_user_id, request_id=str(body.request_id),
        content_version=body.content_version, analysis_generation=body.analysis_generation,
        previous_label=previous, label=body.label, reason=body.reason,
        request_digest=digest, response=response))
    db.commit()
    return response


def wilson_lower(positive, total, z=1.96):
    if total == 0:
        return 0.0
    p = positive / total
    return (p + z*z/(2*total) - z*sqrt((p*(1-p)+z*z/(4*total))/total)) / (1+z*z/total)


def summaries(db, film_ids, settings, window_days=None, now=None):
    now = now or utcnow()
    days = window_days or settings.sentiment_window_days
    cutoff = now - timedelta(days=days)
    rows = db.exec(select(Review.film_id, ReviewSentiment.status, ReviewSentiment.label, func.count())
        .join(ReviewSentiment, Review.id == ReviewSentiment.review_id)
        .where(Review.film_id.in_(film_ids), Review.is_deleted == False,
               Review.moderation_status == "approved", Review.updated_at >= cutoff, Review.updated_at <= now,
               Review.content_version == ReviewSentiment.content_version)
        .group_by(Review.film_id, ReviewSentiment.status, ReviewSentiment.label)).all()
    result = {i: dict(film_id=i, positive=0, neutral=0, negative=0, needs_review=0, pending=0,
                     window_days=days, window_start=cutoff, as_of=now) for i in film_ids}
    for film_id, status, label, count in rows:
        key = label if status == "succeeded" and label in ("positive", "neutral", "negative") else (
            "needs_review" if status == "needs_review" else "pending")
        result[film_id][key] += count
    for item in result.values():
        total = item["positive"] + item["neutral"] + item["negative"]
        item.update(total=total, positive_ratio=item["positive"]/total if total else 0,
                    score=wilson_lower(item["positive"], total),
                    eligible=total >= settings.sentiment_min_reviews,
                    min_reviews=settings.sentiment_min_reviews)
    return result
