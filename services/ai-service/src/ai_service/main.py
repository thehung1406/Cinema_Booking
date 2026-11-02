from contextlib import asynccontextmanager
from secrets import compare_digest
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import JSONResponse
import redis as redis_module
from sqlalchemy import create_engine, func, or_, text
from sqlmodel import Session, select

from cinema_platform.auth import AuthClient, AuthError
from cinema_platform.logging import service_logger
from .config import Settings
from . import chat as chat_service, documents, history
from .models import KnowledgeDocument
from .read_client import ReadSession
from .schemas import ChatRequest, ConversationRead, ConversationDetail, DocumentWrite, DocumentApproval


def create_app(settings=None, *, engine=None, cache=None, auth_transport=None, read_transport=None):
    settings = settings or Settings()
    own_engine = engine is None
    engine = engine or create_engine(settings.database_url, pool_pre_ping=True)
    cache = cache or redis_module.Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=3, socket_connect_timeout=3)
    logger = service_logger("ai")

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(trust_env=False, transport=auth_transport) as auth_http:
            with httpx.Client(trust_env=False, transport=read_transport, timeout=5) as read_http:
                app.state.auth = AuthClient(auth_http, settings.identity_origin, settings.service_key)
                app.state.read_http = read_http
                yield
        if own_engine:
            engine.dispose()

    app = FastAPI(title="Cinema AI", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def context(request, call_next):
        request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Service-Name"] = "ai"
        logger.info("method=%s status=%s request_id=%s", request.method, response.status_code, request_id)
        return response

    def db_session():
        with Session(engine) as db:
            yield db

    async def current_user(authorization: str = Header(default="")):
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "Bearer token required")
        try:
            return await app.state.auth.introspect(token)
        except AuthError as exc:
            raise HTTPException(exc.status_code, "Không thể xác thực truy cập AI") from exc

    async def knowledge_user(user=Depends(current_user)):
        if "knowledge.manage" not in user.permissions:
            raise HTTPException(403, "Bạn không có quyền quản lý tài liệu chatbot")
        return user

    def writes():
        if not settings.writes_enabled:
            raise HTTPException(503, "AI đang chuyển dữ liệu; chưa mở quyền ghi")

    def private(x_service_key: str = Header(default="")):
        if len(settings.service_key) < 32:
            raise HTTPException(503, "Service credential is not configured")
        if not compare_digest(x_service_key.encode(), settings.service_key.encode()):
            raise HTTPException(401, "Invalid service credential")

    @app.get("/health/live")
    def live():
        return {"status": "ok", "service": "ai"}

    @app.get("/health/ready")
    def ready():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            cache.ping()
        except Exception:
            return JSONResponse({"status": "not_ready", "service": "ai"}, status_code=503)
        return {"status": "ready", "service": "ai"}

    @app.get("/internal/v1/migration/state", dependencies=[Depends(private)], include_in_schema=False)
    def migration_state():
        return {"writes_enabled": settings.writes_enabled}

    @app.post("/ai/chat", dependencies=[Depends(writes)])
    def ask(body: ChatRequest, user=Depends(current_user), db=Depends(db_session)):
        reader = ReadSession(app.state.read_http, settings)
        return chat_service.chat(db, user.user_id, body, cache, reader, settings)

    @app.get("/ai/conversations", response_model=list[ConversationRead])
    def conversations(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), user=Depends(current_user), db=Depends(db_session)):
        return history.list_conversations(db, user.user_id, limit, offset)

    @app.get("/ai/conversations/{conversation_id}", response_model=ConversationDetail)
    def conversation(conversation_id: UUID, limit: int = Query(100, ge=1, le=200), before_id: int | None = Query(None, gt=0), user=Depends(current_user), db=Depends(db_session)):
        return history.read_conversation(db, user.user_id, conversation_id, limit, before_id)

    @app.delete("/ai/conversations/{conversation_id}", status_code=204, dependencies=[Depends(writes)])
    def delete_conversation(conversation_id: UUID, user=Depends(current_user), db=Depends(db_session)):
        history.delete_conversation(db, user.user_id, conversation_id, cache)
        return Response(status_code=204)

    @app.get("/admin/documents")
    def document_list(q: str = Query("", max_length=100), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), user=Depends(knowledge_user), db=Depends(db_session)):
        stmt = select(KnowledgeDocument)
        if q:
            stmt = stmt.where(or_(KnowledgeDocument.title.icontains(q, autoescape=True), KnowledgeDocument.source_id.icontains(q, autoescape=True)))
        total = db.exec(select(func.count()).select_from(stmt.subquery())).one()
        return {"items": db.exec(stmt.order_by(KnowledgeDocument.id.desc()).offset(offset).limit(limit)).all(), "total": total}

    @app.get("/admin/documents/{document_id}")
    def document(document_id: int, user=Depends(knowledge_user), db=Depends(db_session)):
        return documents.document_detail(db, document_id)

    @app.post("/admin/documents", dependencies=[Depends(writes)])
    def document_write(body: DocumentWrite, user=Depends(knowledge_user), db=Depends(db_session)):
        return documents.document_write(db, body)

    @app.put("/admin/documents/{document_id}/approval", dependencies=[Depends(writes)])
    def approve(document_id: int, body: DocumentApproval, user=Depends(knowledge_user), db=Depends(db_session)):
        return documents.document_approve(db, document_id, body)

    @app.delete("/admin/documents/{document_id}", dependencies=[Depends(writes)])
    def document_delete(document_id: int, user=Depends(knowledge_user), db=Depends(db_session)):
        return documents.document_delete(db, document_id)

    return app


def application():
    return create_app()
