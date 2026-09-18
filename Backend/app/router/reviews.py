from datetime import date
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.config import settings
from app.models import Review
from app.schemas.ai import ReviewWrite, ReviewEdit, ReviewRead, ModerationWrite
from app.services import review_service as service
from app.utils.dependencies import get_current_user, require_staff

router = APIRouter(tags=["Reviews"])


@router.get("/films/positive-trending")
def trending(theater_id: int | None = Query(None, gt=0), show_date: date | None = None,
             window_days: int = Query(settings.SENTIMENT_WINDOW_DAYS, ge=1, le=365), limit: int = Query(12, ge=1, le=50),
             db: Session = Depends(get_session)):
    return service.positive_films(db, theater_id, show_date, window_days, limit)


@router.get("/films/{film_id}/sentiment-summary")
def summary(film_id: int, window_days: int = Query(settings.SENTIMENT_WINDOW_DAYS, ge=1, le=365), db: Session = Depends(get_session)):
    service.require_film(db, film_id)
    return service.summaries(db, [film_id], window_days)[film_id]


@router.get("/films/{film_id}/reviews", response_model=list[ReviewRead])
def reviews(film_id: int, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
            db: Session = Depends(get_session)):
    service.require_film(db, film_id)
    rows = db.exec(select(Review).where(Review.film_id == film_id, Review.is_deleted == False,
        Review.moderation_status == "approved").order_by(Review.updated_at.desc(), Review.id.desc()).offset(skip).limit(limit)).all()
    return [service.present_review(db, r) for r in rows]


@router.get("/films/{film_id}/reviews/mine", response_model=ReviewRead | None)
def my_review(film_id: int, db: Session = Depends(get_session), user=Depends(get_current_user)):
    row = db.exec(select(Review).where(Review.film_id == film_id, Review.user_id == user.id, Review.is_deleted == False)).first()
    return service.present_review(db, row, user.id) if row else None


@router.post("/films/{film_id}/reviews", response_model=ReviewRead, status_code=201)
def create(film_id: int, body: ReviewWrite, db: Session = Depends(get_session), user=Depends(get_current_user)):
    return service.present_review(db, service.create_review(db, film_id, user.id, body.content), user.id)


@router.patch("/reviews/{review_id}", response_model=ReviewRead)
def edit(review_id: int, body: ReviewEdit, db: Session = Depends(get_session), user=Depends(get_current_user)):
    return service.present_review(db, service.edit_review(db, review_id, user.id, body), user.id)


@router.delete("/reviews/{review_id}", status_code=204)
def remove(review_id: int, db: Session = Depends(get_session), user=Depends(get_current_user)):
    service.delete_review(db, review_id, user.id)
    return Response(status_code=204)


@router.get("/reviews/moderation/pending", response_model=list[ReviewRead])
def pending(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
            db: Session = Depends(get_session), staff=Depends(require_staff)):
    rows = db.exec(select(Review).where(Review.is_deleted == False, Review.moderation_status == "pending")
        .order_by(Review.updated_at, Review.id).offset(skip).limit(limit)).all()
    return [service.present_review(db, r, staff.id) for r in rows]


@router.patch("/reviews/{review_id}/moderation", response_model=ReviewRead)
def moderate(review_id: int, body: ModerationWrite, db: Session = Depends(get_session), staff=Depends(require_staff)):
    return service.present_review(db, service.moderate_review(db, review_id, body), staff.id)


@router.post("/reviews/{review_id}/retry", response_model=ReviewRead)
def retry(review_id: int, db: Session = Depends(get_session), staff=Depends(require_staff)):
    review = service.locked_review(db, review_id)
    if review.moderation_status != "approved":
        raise HTTPException(409, "Cần duyệt đánh giá trước khi phân tích lại")
    service.invalidate(db, review)
    db.commit()
    service.enqueue(review.id, review.content_version)
    return service.present_review(db, review, staff.id)
