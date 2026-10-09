"""Persistent, user-owned AI conversations and their message history."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, Index, Integer, JSON, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.ai import utcnow

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class AIConversation(SQLModel, table=True):
    __tablename__ = "ai_conversations"
    __table_args__ = (Index("ix_ai_conversations_user_updated", "user_id", "updated_at"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE")
    title: str = Field(max_length=200)
    context: dict = Field(default_factory=dict, sa_column=Column(JSON_TYPE, nullable=False))
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class AIMessage(SQLModel, table=True):
    __tablename__ = "ai_messages"
    __table_args__ = (
        Index("ix_ai_messages_conversation_id", "conversation_id", "id"),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_ai_messages_role"),
    )

    id: int | None = Field(default=None, sa_column=Column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True))
    conversation_id: UUID = Field(foreign_key="ai_conversations.id", ondelete="CASCADE")
    role: str = Field(max_length=20)
    content: str = Field(sa_column=Column(Text, nullable=False))
    # SQLAlchemy reserves the Python attribute "metadata".
    details: dict = Field(default_factory=dict, sa_column=Column("metadata", JSON_TYPE, nullable=False))
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
