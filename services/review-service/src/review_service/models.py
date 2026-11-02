from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("user_id", "film_id", name="uq_review_user_film"),
        Index("ix_reviews_film_window", "film_id", "updated_at"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer)  # External identity, no cross-store FK.
    film_id: Mapped[int] = mapped_column(Integer)  # Validated through read API.
    content: Mapped[str] = mapped_column(String(3000))
    content_version: Mapped[int] = mapped_column(default=1)
    moderation_status: Mapped[str] = mapped_column(String(20), default="pending")
    is_deleted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    event_version: Mapped[int] = mapped_column(default=0, server_default="0")


class ReviewSentiment(Base):
    __tablename__ = "review_sentiments"
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"), primary_key=True)
    content_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    label: Mapped[str | None] = mapped_column(String(20))
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    model_version: Mapped[str | None] = mapped_column(String(200))
    attempts: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    analysis_generation: Mapped[int] = mapped_column(default=1, server_default="1")

    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
