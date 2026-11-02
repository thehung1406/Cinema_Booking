"""Versioned wire envelope and local SQL messaging state."""

from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc)


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9]+\.v[1-9][0-9]*$")
    occurred_at: AwareDatetime = Field(default_factory=utcnow)
    producer: str = Field(min_length=1, max_length=100)
    aggregate_id: str = Field(min_length=1, max_length=150)
    aggregate_version: int = Field(gt=0)
    correlation_id: str = Field(min_length=1, max_length=150)
    causation_id: str | None = Field(default=None, max_length=150)
    data: dict


def fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


class MessagingBase(DeclarativeBase):
    pass


class OutboxRecord(MessagingBase):
    __tablename__ = "outbox_events"
    __table_args__ = (UniqueConstraint("event_type", "aggregate_id", "aggregate_version", name="uq_outbox_aggregate_event"),)
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100))
    aggregate_id: Mapped[str] = mapped_column(String(150))
    aggregate_version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    destination: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InboxRecord(MessagingBase):
    __tablename__ = "inbox_events"
    consumer: Mapped[str] = mapped_column(String(100), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload_sha256: Mapped[str] = mapped_column(String(64))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReplayAudit(MessagingBase):
    __tablename__ = "message_replay_audits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    record_id: Mapped[str] = mapped_column(String(36), index=True)
    actor: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
