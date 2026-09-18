from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.core.database import get_session
from app.schemas.ai import ChatRequest
from app.services.chat_service import chat
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/ai", tags=["AI assistant"])


@router.post("/chat")
def ask(body: ChatRequest, db: Session = Depends(get_session), user=Depends(get_current_user)):
    return chat(db, user.id, body)
