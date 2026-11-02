from datetime import datetime
from pydantic import BaseModel, ConfigDict
from cinema_platform.events import EventEnvelope
from cinema_platform.outbox import enqueue


class ReviewFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_id: int
    film_id: int
    content_version: int
    moderation_status: str
    is_deleted: bool
    updated_at: datetime
    analysis_status: str
    label: str | None
    model_version: str | None


def changed(db, review, result, event_type="ReviewChanged.v1"):
    review.event_version += 1
    fact = ReviewFact(review_id=review.id, film_id=review.film_id,
        content_version=review.content_version, moderation_status=review.moderation_status,
        is_deleted=review.is_deleted, updated_at=review.updated_at,
        analysis_status=result.status, label=result.label, model_version=result.model_version)
    enqueue(db, EventEnvelope(event_type=event_type, producer="review", aggregate_id=str(review.id),
        aggregate_version=review.event_version, correlation_id=f"review:{review.id}",
        data=fact.model_dump(mode="json")), "public")
