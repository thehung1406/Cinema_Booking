from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from sqlmodel import Session
from app.core.database import get_session
from app.schemas.ai import ChatRequest, ConversationRead, ConversationDetail
from app.services.chat_service import chat
from app.services.chat_history_service import list_conversations, read_conversation, delete_conversation
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/ai", tags=["AI assistant"])


@router.post("/chat")
def ask(body: ChatRequest, db: Session = Depends(get_session), user=Depends(get_current_user)):
    return chat(db, user.id, body)


@router.get("/conversations", response_model=list[ConversationRead])
def history(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
            db: Session = Depends(get_session), user=Depends(get_current_user)):
    return list_conversations(db, user.id, limit, offset)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation(conversation_id: UUID, limit: int = Query(100, ge=1, le=200),
                 before_id: int | None = Query(None, gt=0),
                 db: Session = Depends(get_session), user=Depends(get_current_user)):
    return read_conversation(db, user.id, conversation_id, limit, before_id)


@router.delete("/conversations/{conversation_id}", status_code=204)
def remove_conversation(conversation_id: UUID, db: Session = Depends(get_session),
                        user=Depends(get_current_user)):
    delete_conversation(db, user.id, conversation_id)
    return Response(status_code=204)
