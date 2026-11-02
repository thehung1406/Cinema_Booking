"""Aggregates are read from current rows, so retries and edits cannot double count."""
from datetime import timedelta
from math import sqrt

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from .config import Settings
from .models import Review, ReviewSentiment, utcnow
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
