"""Aggregates are read from current rows, so retries and edits cannot double count."""
from datetime import timedelta
from math import sqrt

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.core.config import settings
from app.models import Review, ReviewSentiment, Film, Booking, Showtime, CinemaRoom, Theater
from app.models.ai import utcnow


def require_film(db, film_id):
    from app.services.catalog_remote import get_film
    film = get_film(db, film_id)
    if film is None or film.deleted_at is not None:
        raise HTTPException(404, "Phim không tồn tại")
    return film


def locked_review(db, review_id):
    review = db.exec(select(Review).where(Review.id == review_id).with_for_update()).first()
    if review is None or review.is_deleted:
        raise HTTPException(404, "Đánh giá không tồn tại")
    return review


def invalidate(db, review):
    from app.utils.review_ownership import require_legacy_review_owner
    require_legacy_review_owner(db)
    result = db.get(ReviewSentiment, review.id)
    if result is None:
        result = ReviewSentiment(review_id=review.id, content_version=review.content_version)
    result.content_version = review.content_version
    result.status = "pending"
    result.label = None
    result.scores = {}
    result.model_version = None
    result.attempts = 0
    result.updated_at = utcnow()
    db.add(result)


def enqueue(review_id, content_version):
    # The persisted pending row is the outbox. Beat recovers broker outages.
    try:
        from app.worker.ai_tasks import analyze_review
        analyze_review.apply_async(args=[review_id, content_version], retry=False)
    except Exception:
        pass  # Never lose a saved review because Redis/Celery is unavailable.


def create_review(db, film_id, user_id, content):
    from app.utils.review_ownership import require_legacy_review_owner
    require_legacy_review_owner(db)
    require_film(db, film_id)
    review = db.exec(select(Review).where(Review.user_id == user_id, Review.film_id == film_id).with_for_update()).first()
    if review and not review.is_deleted:
        raise HTTPException(409, "Bạn đã có đánh giá cho phim này; hãy chỉnh sửa đánh giá.")
    if review:
        review.content_version += 1
        review.content = content
        review.is_deleted = False
        review.updated_at = utcnow()
    else:
        review = Review(user_id=user_id, film_id=film_id, content=content)
    review.moderation_status = "approved" if settings.REVIEW_AUTO_APPROVE else "pending"
    db.add(review)
    try:
        db.flush()
        invalidate(db, review)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Tài khoản đã có đánh giá cho phim này")
    db.refresh(review)
    if review.moderation_status == "approved":
        enqueue(review.id, review.content_version)
    return review


def edit_review(db, review_id, user_id, body):
    from app.utils.review_ownership import require_legacy_review_owner
    require_legacy_review_owner(db)
    review = locked_review(db, review_id)
    if review.user_id != user_id:
        raise HTTPException(403, "Bạn chỉ được sửa đánh giá của mình")
    if review.content_version != body.content_version:
        raise HTTPException(409, "Đánh giá đã thay đổi. Vui lòng tải lại.")
    review.content = body.content
    review.content_version += 1
    review.updated_at = utcnow()
    review.moderation_status = "approved" if settings.REVIEW_AUTO_APPROVE else "pending"
    invalidate(db, review)
    db.add(review)
    db.commit()
    db.refresh(review)
    if review.moderation_status == "approved":
        enqueue(review.id, review.content_version)
    return review


def delete_review(db, review_id, user_id):
    from app.utils.review_ownership import require_legacy_review_owner
    require_legacy_review_owner(db)
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
    from app.utils.review_ownership import require_legacy_review_owner
    require_legacy_review_owner(db)
    review = locked_review(db, review_id)
    if review.content_version != body.content_version:
        raise HTTPException(409, "Nội dung đã thay đổi; cần duyệt lại phiên bản mới")
    review.moderation_status = body.status
    invalidate(db, review)
    db.add(review)
    db.commit()
    db.refresh(review)
    if body.status == "approved":
        enqueue(review.id, review.content_version)
    return review


def present_review(db, review, viewer_id=None):
    result = db.get(ReviewSentiment, review.id)
    from app.services.identity_remote import contact
    user = contact(db, review.user_id)
    from app.utils.cinema_ownership import get_owner as cinema_owner
    if cinema_owner(db)=="service":
        from app.models.sales import SalesConfiguration as Config
        from sqlalchemy import and_
        purchase=select(Booking.id).join(Config,and_(Config.showtime_id==Booking.showtime_id,Config.sales_version==Booking.sales_version)).where(Config.film_id==review.film_id)
    else: purchase=select(Booking.id).join(Showtime,Showtime.id==Booking.showtime_id).where(Showtime.film_id==review.film_id)
    verified=db.exec(purchase.where(Booking.user_id==review.user_id,Booking.payment_status=="PAID").limit(1)).first() is not None
    current = result and result.content_version == review.content_version
    return dict(id=review.id, content=review.content, content_version=review.content_version,
                moderation_status=review.moderation_status, updated_at=review.updated_at,
                analysis_status=result.status if current else "pending",
                sentiment=result.label if current and result.status == "succeeded" else None,
                author=user.username if user else "Khán giả", is_owner=viewer_id == review.user_id,
                verified_purchase=verified)


def wilson_lower(positive, total, z=1.96):
    if total == 0:
        return 0.0
    p = positive / total
    return (p + z*z/(2*total) - z*sqrt((p*(1-p)+z*z/(4*total))/total)) / (1+z*z/total)


def summaries(db, film_ids, window_days=None, now=None):
    now = now or utcnow()
    days = window_days or settings.SENTIMENT_WINDOW_DAYS
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
                    eligible=total >= settings.SENTIMENT_MIN_REVIEWS,
                    min_reviews=settings.SENTIMENT_MIN_REVIEWS)
    return result


def future_showtimes(db, film_id=None, theater_id=None, show_date=None, evening=False):
    from app.utils.cinema_ownership import get_owner as cinema_owner
    if cinema_owner(db)=="service":
        from app.services.sales_service import future_query
        return future_query(film_id,theater_id,show_date,evening)
    from datetime import datetime, time
    from zoneinfo import ZoneInfo
    from sqlalchemy import or_, and_
    from app.models.showtime import ShowtimeStatus
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    stmt = select(Showtime).join(CinemaRoom, Showtime.room_id == CinemaRoom.id).join(Theater).where(
        Theater.deleted_at.is_(None),
        CinemaRoom.deleted_at.is_(None), CinemaRoom.status == "ACTIVE",
        Showtime.status == ShowtimeStatus.ACTIVE,
        or_(Showtime.show_date > now.date(), and_(Showtime.show_date == now.date(), Showtime.start_time > now.time().replace(tzinfo=None))))
    from app.utils.catalog_ownership import get_owner
    owner = get_owner(db)
    if owner == "monolith":
        stmt = stmt.join(Film, Film.id == Showtime.film_id).where(Film.deleted_at.is_(None))
    elif owner == "maintenance": raise HTTPException(503, "Catalog đang chuyển dữ liệu")
    if film_id is not None:
        stmt = stmt.where(Showtime.film_id == film_id)
    if theater_id is not None:
        stmt = stmt.where(CinemaRoom.theater_id == theater_id)
    if show_date is not None:
        stmt = stmt.where(Showtime.show_date == show_date)
    if evening:
        stmt = stmt.where(Showtime.start_time >= time(18))
    return stmt.order_by(Showtime.show_date, Showtime.start_time, Showtime.id)


def positive_films(db, theater_id=None, show_date=None, window_days=None, limit=12, evening=False):
    from app.utils.review_ownership import get_owner
    owner = get_owner(db)
    if owner != "monolith":
        if owner != "service":
            raise HTTPException(503, "Review đang chuyển dữ liệu")
        from app.services.review_remote import positive_films as remote
        db.rollback()  # No legacy connection held while Review calls the read facade.
        return remote(theater_id, show_date, window_days, limit, evening)
    candidates = future_showtimes(db, theater_id=theater_id, show_date=show_date, evening=evening).subquery()
    from app.utils.catalog_ownership import get_owner as catalog_owner
    if catalog_owner(db) == "service":
        from app.services.catalog_remote import film_batch
        films = list(film_batch(db.exec(select(candidates.c.film_id).distinct()).all()).values())
    else:
        films = db.exec(select(Film).where(Film.id.in_(select(candidates.c.film_id).distinct()))).all()
    stats = summaries(db, [f.id for f in films], window_days)
    ranked = [dict(film_id=f.id, title=f.title, image=f.image, summary=stats[f.id],
                   booking_url=f"/ticket-booking?filmId={f.id}") for f in films if stats[f.id]["eligible"]]
    ranked.sort(key=lambda x: (-x["summary"]["score"], -x["summary"]["total"], x["film_id"]))
    return ranked[:limit]
