from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class AIConversation(Base):
    __tablename__ = "ai_conversations"
    __table_args__ = (Index("ix_ai_conversations_user_updated", "user_id", "updated_at"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    # External identity, verified through AuthClient; no FK into another service.
    user_id: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    context: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AIMessage(Base):
    __tablename__ = "ai_messages"
    __table_args__ = (
        Index("ix_ai_messages_conversation_id", "conversation_id", "id"),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_ai_messages_role"),
    )
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("ai_conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column("metadata", JSON().with_variant(JSONB(), "postgresql"), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeDocument(Base):
    __tablename__ = "ai_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(50))
    source_url: Mapped[str] = mapped_column(String(500))
    approved: Mapped[bool] = mapped_column(default=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def model_dump(self):
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}

    provenance: Mapped[dict] = mapped_column(JSON, default=dict)


class KnowledgeChunk(Base):
    __tablename__ = "ai_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("ai_documents.id"), index=True)
    content: Mapped[str] = mapped_column(String(3000))
    embedding: Mapped[list] = mapped_column(JSON)
    embedding_version: Mapped[str] = mapped_column(String(100))
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
