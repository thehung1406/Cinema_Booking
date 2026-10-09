"""History queries always scope conversations to the authenticated user."""
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete
from sqlmodel import select

from app.core.redis import redis_client
from app.models import AIConversation, AIMessage


def owned_conversation(db, user_id: int, conversation_id: UUID):
    conversation = db.exec(select(AIConversation).where(
        AIConversation.id == conversation_id, AIConversation.user_id == user_id)).first()
    if conversation is None:
        raise HTTPException(404, "Không tìm thấy hội thoại.")
    return conversation


def list_conversations(db, user_id, limit, offset):
    return db.exec(select(AIConversation).where(AIConversation.user_id == user_id)
        .order_by(AIConversation.updated_at.desc(), AIConversation.id.desc())
        .offset(offset).limit(limit)).all()


def read_conversation(db, user_id, conversation_id, limit, before_id=None):
    conversation = owned_conversation(db, user_id, conversation_id)
    query = select(AIMessage).where(AIMessage.conversation_id == conversation.id)
    if before_id is not None:
        query = query.where(AIMessage.id < before_id)
    rows = db.exec(query.order_by(AIMessage.id.desc()).limit(limit + 1)).all()
    has_more = len(rows) > limit
    messages = list(reversed(rows[:limit]))
    return dict(id=conversation.id, title=conversation.title,
        context=conversation.context.get("context", {}),
        created_at=conversation.created_at, updated_at=conversation.updated_at,
        messages=[dict(id=m.id, role=m.role, content=m.content,
                       metadata=m.details, created_at=m.created_at) for m in messages],
        next_before_id=messages[0].id if has_more else None)


def delete_conversation(db, user_id, conversation_id, redis=None):
    conversation = owned_conversation(db, user_id, conversation_id)
    # Explicit deletion also works for SQLite tests without FK enforcement.
    db.execute(delete(AIMessage).where(AIMessage.conversation_id == conversation.id))
    db.delete(conversation)
    db.commit()
    try:
        (redis if redis is not None else redis_client).delete(f"ai:context:{user_id}:{conversation_id}")
    except Exception:
        pass  # DB ownership is authoritative even if a stale cache entry remains.
