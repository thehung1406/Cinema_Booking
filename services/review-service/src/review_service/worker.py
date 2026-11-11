"""DB-backed inference queue with recoverable leases; no booking resources or Celery."""
import logging
import time
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import or_
from sqlmodel import Session, select
from .config import Settings
from .models import Review, ReviewSentiment, utcnow
from .events import changed
from .predictor import load_predictor, validate_scores


def process_one(engine, settings, predictor=None):
    if not settings.writes_enabled or (settings.sentiment_backend == "disabled" and predictor is None):
        return False
    now, token = utcnow(), str(uuid4())
    with Session(engine) as db, db.begin():
        row = db.exec(select(ReviewSentiment, Review.content).join(Review, Review.id == ReviewSentiment.review_id).where(
            Review.is_deleted == False, Review.moderation_status == "approved",
            ReviewSentiment.content_version == Review.content_version,
            ReviewSentiment.status.in_(["pending", "failed"]), ReviewSentiment.attempts < settings.max_attempts,
            or_(ReviewSentiment.lease_until.is_(None), ReviewSentiment.lease_until <= now),
            or_(ReviewSentiment.status == "pending", ReviewSentiment.updated_at <= now - timedelta(seconds=settings.retry_seconds))
        ).order_by(ReviewSentiment.updated_at, ReviewSentiment.review_id).limit(1)
            .with_for_update(of=ReviewSentiment, skip_locked=True)).first()
        if not row:
            return False
        result, content = row
        review_id, version, generation = result.review_id, result.content_version, result.analysis_generation
        result.lease_token, result.lease_until = token, now + timedelta(minutes=5)
        result.attempts += 1
    # No DB connection held during inference. A crashed worker is recovered after lease expiry.
    try:
        predict, model_version = predictor or load_predictor(settings.sentiment_backend, settings.sentiment_model_path)
        scores = predict(content)
        validate_scores(scores)
        if not isinstance(model_version, str) or not model_version or len(model_version) > 200:
            raise ValueError("Invalid model version")
        label = max(scores, key=scores.get)
        status = "succeeded" if scores[label] >= settings.sentiment_review_threshold else "needs_review"
    except Exception:
        scores, label, model_version, status = {}, None, None, "failed"
    with Session(engine) as db, db.begin():
        review = db.exec(select(Review).where(Review.id == review_id).with_for_update()).first()
        result = db.get(ReviewSentiment, review_id, with_for_update=True)
        if (not review or not result or review.is_deleted or review.moderation_status != "approved"
                or review.content_version != version or result.content_version != version
                or result.analysis_generation != generation or result.lease_token != token):
            return "stale"
        result.status, result.scores, result.label, result.model_version = status, scores, label, model_version
        result.predicted_label = label
        result.decision_source = "model" if status in {"succeeded", "needs_review"} else None
        result.confirmed_by_user_id = result.confirmed_at = result.confirmation_note = None
        result.lease_token = result.lease_until = None
        result.updated_at = utcnow()
        changed(db, review, result, "ReviewSentimentUpdated.v1")
    return status


def main():
    from sqlalchemy import create_engine
    settings = Settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    logger = logging.getLogger("cinema.review.worker")
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            if not process_one(engine, settings):
                time.sleep(2)
        except Exception as exc:
            logger.error("worker_failed error_type=%s", type(exc).__name__)
            time.sleep(5)


if __name__ == "__main__":
    main()
