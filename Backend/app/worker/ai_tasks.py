from sqlmodel import Session, select
from app.core.database import engine
from app.core.config import settings
from app.models import Review, ReviewSentiment
from app.services.sentiment_service import process_review
from app.worker.celery_config import celery_app


@celery_app.task(name="app.worker.ai_tasks.analyze_review", soft_time_limit=90, time_limit=120, ignore_result=True)
def analyze_review(review_id, content_version):
    if settings.SENTIMENT_BACKEND == "disabled":
        return "pending"
    with Session(engine) as db:
        return process_review(db, review_id, content_version)


@celery_app.task(name="app.worker.ai_tasks.retry_pending_reviews", ignore_result=True)
def retry_pending_reviews():
    if settings.SENTIMENT_BACKEND == "disabled":
        return 0
    with Session(engine) as db:
        rows = db.exec(select(Review.id, Review.content_version).join(ReviewSentiment).where(
            Review.is_deleted == False, Review.moderation_status == "approved",
            Review.content_version == ReviewSentiment.content_version,
            ReviewSentiment.status.in_(["pending", "failed"]), ReviewSentiment.attempts < 5)
            .order_by(ReviewSentiment.updated_at).limit(100)).all()
    for review_id, version in rows:
        analyze_review.apply_async(args=[review_id, version], retry=False)
    return len(rows)
