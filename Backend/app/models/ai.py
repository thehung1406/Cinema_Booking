"""Versioned reviews and curated knowledge. AI artifacts are stored outside the DB."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, JSON, UniqueConstraint, Index
from sqlmodel import Field, SQLModel


def utcnow():
    return datetime.now(timezone.utc)


class Review(SQLModel, table=True):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "film_id", name="uq_review_user_film"),
        Index("ix_reviews_film_window", "film_id", "updated_at"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    film_id: int = Field(foreign_key="films.id")
    content: str = Field(max_length=3000)
    content_version: int = Field(default=1)
    moderation_status: str = Field(default="pending", max_length=20)
    is_deleted: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class ReviewSentiment(SQLModel, table=True):
    __tablename__ = "review_sentiments"
    # One current result: retries replace, never increment aggregate counters.
    review_id: int = Field(foreign_key="reviews.id", primary_key=True)
    content_version: int
    status: str = Field(default="pending", max_length=20, index=True)
    label: Optional[str] = Field(default=None, max_length=20)
    scores: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    model_version: Optional[str] = Field(default=None, max_length=200)
    attempts: int = Field(default=0)
    updated_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class KnowledgeDocument(SQLModel, table=True):
    __tablename__ = "ai_documents"
    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: str = Field(max_length=100, unique=True)
    title: str = Field(max_length=200)
    version: str = Field(max_length=50)
    source_url: str = Field(max_length=500)
    approved: bool = Field(default=False)
    effective_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class KnowledgeChunk(SQLModel, table=True):
    __tablename__ = "ai_chunks"
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="ai_documents.id", index=True)
    content: str = Field(max_length=3000)
    embedding: list[float] = Field(sa_column=Column(JSON, nullable=False))
    embedding_version: str = Field(max_length=100)
