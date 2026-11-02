"""Technical cutover state, separate from the 28 business SQLModel entities."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class OwnershipBase(DeclarativeBase):
    pass


class DomainOwnership(OwnershipBase):
    __tablename__ = "domain_ownership"
    domain: Mapped[str] = mapped_column(String(100), primary_key=True)
    owner: Mapped[str] = mapped_column(String(20), default="monolith")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class OwnershipAudit(OwnershipBase):
    __tablename__ = "domain_ownership_audits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    domain: Mapped[str] = mapped_column(String(100))
    old_owner: Mapped[str] = mapped_column(String(20))
    new_owner: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
