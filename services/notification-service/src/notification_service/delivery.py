"""Durable inbox + delivery job; SMTP never runs while consuming a broker event."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from cinema_platform.events import EventEnvelope, InboxRecord, fingerprint, utcnow
from cinema_platform.logging import service_logger
from .models import DeliveryAttempt, DeliveryJob

CONSUMER = "notification.email.v1"
EMAIL_EVENT = "BookingConfirmationEmailRequested.v1"
logger = service_logger("notification")


class SeatSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seat_name: str = Field(min_length=1, max_length=100)
    seat_id: int | None = None
    seat_type: str | None = None
    price: Decimal | None = None


class FoodSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: int = Field(ge=1, le=20)
    name: str = Field(min_length=1, max_length=150)
    line_total: Decimal = Field(gt=0)
    food_item_id: int | None = None
    category: str | None = None
    unit_price: Decimal | None = None
    components: list[dict] = Field(default_factory=list)


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bookingId: int = Field(gt=0)
    fullName: str | None = None
    filmTitle: str | None = None
    theaterName: str | None = None
    roomName: str | None = None
    showDate: str | None = None
    startTime: str | None = None
    totalAmount: Decimal = Field(gt=0)
    seats: list[SeatSnapshot] = Field(min_length=1, max_length=200)
    foodItems: list[FoodSnapshot] = Field(default_factory=list, max_length=50)


class EmailData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to_email: EmailStr
    booking_detail: Snapshot


def receive(session, event: EventEnvelope) -> str:
    if event.event_type != EMAIL_EVENT or event.aggregate_version != 1:
        raise ValueError("Unsupported notification event/version")
    data = EmailData.model_validate(event.data)
    if event.aggregate_id != f"booking:{data.booking_detail.bookingId}":
        raise ValueError("Aggregate and booking snapshot disagree")
    digest = fingerprint(event.model_dump(mode="json"))
    claim = session.execute(insert(InboxRecord).values(
        consumer=CONSUMER, event_id=str(event.event_id), payload_sha256=digest,
    ).on_conflict_do_nothing().returning(InboxRecord.event_id)).scalar_one_or_none()
    if claim is None:
        original = session.get(InboxRecord, (CONSUMER, str(event.event_id)))
        if original.payload_sha256 != digest:
            raise ValueError("Event ID reused with a different payload")
        return "duplicate"
    payload = data.model_dump(mode="json")
    payload_digest = fingerprint(payload)
    dedup_key = f"booking:{data.booking_detail.bookingId}:confirmation:v1"
    job_id = session.execute(insert(DeliveryJob).values(
        id=str(event.event_id), dedup_key=dedup_key,
        booking_id=data.booking_detail.bookingId, payload=payload, payload_sha256=payload_digest,
    ).on_conflict_do_nothing(index_elements=[DeliveryJob.dedup_key]).returning(DeliveryJob.id)).scalar_one_or_none()
    if job_id is None:
        original = session.execute(select(DeliveryJob).where(DeliveryJob.dedup_key == dedup_key)).scalar_one()
        if original.payload_sha256 != payload_digest:
            raise ValueError("Booking confirmation reused with different delivery content")
    return "accepted" if job_id else "duplicate"


def dispatch_one(engine, settings, sender) -> bool:
    now = utcnow()
    with Session(engine) as db, db.begin():
        job = db.execute(select(DeliveryJob).where(or_(
            and_(DeliveryJob.status.in_(["PENDING", "RETRY"]), DeliveryJob.next_attempt_at <= now),
            and_(DeliveryJob.status == "PROCESSING", DeliveryJob.lease_until <= now),
        )).order_by(DeliveryJob.created_at).limit(1).with_for_update(skip_locked=True)).scalar_one_or_none()
        if job is None:
            return False
        if job.attempts >= settings.max_attempts:
            job.status, job.last_error = "DEAD", "DeliveryAttemptsExhausted"
            return True
        job.status, job.lease_token = "PROCESSING", str(uuid4())
        job.lease_until = now + timedelta(seconds=settings.lease_seconds)
        job.attempts += 1
        job_id, lease_token, payload = job.id, job.lease_token, job.payload
    error = None
    try:
        sender(EmailData.model_validate(payload), settings)
    except Exception as exc:
        error = type(exc).__name__[:100]
    with Session(engine) as db, db.begin():
        job = db.get(DeliveryJob, job_id, with_for_update=True)
        if job.lease_token != lease_token:
            return True
        job.last_error, job.lease_token, job.lease_until = error, None, None
        if error is None:
            job.status, job.sent_at = "SENT", utcnow()
        else:
            job.status = "DEAD" if job.attempts >= settings.max_attempts else "RETRY"
            job.next_attempt_at = utcnow() + timedelta(seconds=min(2 ** job.attempts, 300))
        db.add(DeliveryAttempt(job_id=job_id, outcome=job.status, error_type=error))
        status, attempts = job.status, job.attempts
    logger.info("delivery_job=%s status=%s attempts=%s", job_id, status, attempts)
    return True


def retry_job(db, job_id: str, actor: str, reason: str):
    job = db.get(DeliveryJob, job_id, with_for_update=True)
    if job is None:
        raise LookupError("Delivery not found")
    if job.status != "DEAD":
        raise ValueError("Only DEAD delivery jobs may be manually retried")
    job.status, job.attempts, job.next_attempt_at, job.last_error = "PENDING", 0, utcnow(), None
    job.lease_token, job.lease_until = None, None
    db.add(DeliveryAttempt(job_id=job_id, outcome="OPERATOR_RETRY", actor=actor, reason=reason))
