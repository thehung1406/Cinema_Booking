"""Publish the old pending queue and requeue uncertain model results once."""
from sqlalchemy import create_engine, or_
from sqlmodel import Session, select

from . import service
from .config import Settings
from .events import changed
from .models import Review, ReviewSentiment


def backfill(engine):
    count = 0
    while True:
        with Session(engine) as db, db.begin():
            review = db.exec(select(Review).outerjoin(ReviewSentiment).where(
                Review.is_deleted == False,
                or_(Review.moderation_status == "pending",
                    (Review.moderation_status == "approved") & (ReviewSentiment.status == "needs_review")),
            ).order_by(Review.id).limit(1).with_for_update(of=Review)).first()
            if review is None:
                return count
            result = db.get(ReviewSentiment, review.id, with_for_update=True)
            # A concurrent run may have migrated this row while we waited for its lock.
            if review.is_deleted or not (review.moderation_status == "pending" or (
                review.moderation_status == "approved" and result is not None and result.status == "needs_review"
            )):
                continue
            review.moderation_status = "approved"
            if result is None or result.status == "needs_review" or result.content_version != review.content_version:
                service.invalidate(db, review)
            else:
                changed(db, review, result)
            db.add(review)
        count += 1


def main():
    settings = Settings()
    if not settings.writes_enabled:
        raise RuntimeError("Review writes must be enabled before publication backfill")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        print(f"Updated {backfill(engine)} reviews")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
