"""Publish only committed events; publisher confirm precedes local published marker."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .events import EventEnvelope, OutboxRecord, ReplayAudit, utcnow


def enqueue(session: Session, event: EventEnvelope, destination: str):
    if destination not in {"public", "notification"}:
        raise ValueError("Unknown integration destination")
    row = OutboxRecord(
        event_id=str(event.event_id), event_type=event.event_type,
        aggregate_id=event.aggregate_id, aggregate_version=event.aggregate_version,
        payload=event.model_dump(mode="json"), destination=destination,
    )
    session.add(row)
    session.flush()
    return row


def relay_one(engine, publish, *, max_attempts=20,event_types=None) -> bool:
    """Network call holds only an outbox row lock, never a booking/seat lock."""
    with Session(engine) as session, session.begin():
        row = session.execute(select(OutboxRecord).where(
            OutboxRecord.status == "PENDING", OutboxRecord.available_at <= utcnow(),
            *([OutboxRecord.event_type.in_(event_types)] if event_types else []),
        ).order_by(OutboxRecord.created_at, OutboxRecord.event_id).limit(1).with_for_update(skip_locked=True)).scalar_one_or_none()
        if row is None:
            return False
        row.attempts += 1
        try:
            publish(row.destination, EventEnvelope.model_validate(row.payload))
        except Exception as exc:
            # Store only the error class, never AMQP URLs, recipients or payloads.
            row.last_error = type(exc).__name__[:100]
            row.available_at = utcnow() + timedelta(seconds=min(2 ** min(row.attempts, 9), 300))
            if row.attempts >= max_attempts:
                row.status = "BLOCKED"
        else:
            row.status, row.published_at, row.last_error = "PUBLISHED", utcnow(), None
    return True


def replay(session, event_id: str, actor: str, reason: str):
    if not reason.strip() or len(reason) > 500:
        raise ValueError("An audit reason of 1-500 characters is required")
    row = session.get(OutboxRecord, event_id, with_for_update=True)
    if row is None or row.status == "PUBLISHED":
        raise ValueError("Only unpublished events can be retried")
    row.status, row.attempts, row.available_at, row.last_error = "PENDING", 0, utcnow(), None
    session.add(ReplayAudit(record_id=event_id, actor=actor, reason=reason))
