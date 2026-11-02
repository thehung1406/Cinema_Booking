from datetime import datetime, timezone
from sqlalchemy import String, Integer, BigInteger, DateTime, JSON, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def now():
    return datetime.now(timezone.utc)


class Projection(Base):
    __tablename__ = "report_facts"
    source: Mapped[str] = mapped_column(String(30), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), primary_key=True)
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    version: Mapped[int] = mapped_column(BigInteger)
    deleted: Mapped[bool] = mapped_column(Boolean)
    fact: Mapped[dict] = mapped_column(JSON)
    sha256: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SourceState(Base):
    __tablename__ = "report_sources"
    source: Mapped[str] = mapped_column(String(30), primary_key=True)
    generation: Mapped[str] = mapped_column(String(36))
    bootstrapped: Mapped[bool] = mapped_column(Boolean, default=False)
    snapshot_id: Mapped[str | None] = mapped_column(String(36))
    snapshot_sha256: Mapped[str | None] = mapped_column(String(64))
    snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checkpoint_version: Mapped[int] = mapped_column(BigInteger, default=0)
    checkpoint_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
