"""HTTP routes and request dependencies for this owner. App lifecycle stays in main."""

from secrets import compare_digest

from uuid import UUID

from fastapi import Depends, Header, HTTPException, Query, Response

from fastapi.responses import JSONResponse

from sqlalchemy import func, or_, text

from sqlmodel import Session, select

from cinema_platform.auth import AuthError

from .. import chat as chat_service, documents, history, knowledge_versions

from ..models import KnowledgeDocument

from ..read_client import ReadSession

from ..schemas import (
    ChatRequest,
    ConversationRead,
    ConversationDetail,
    DocumentWrite,
    DocumentApproval,
    DocumentRevisionWrite,
    DocumentRevisionPublish,
)

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Literal


class KnowledgeSearch(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    scope: Literal["policy", "film_education", "reference"] = "policy"
    strategy: Literal["lexical", "bm25", "dense", "hybrid", "rerank"] = "bm25"
    limit: int = Field(default=5, ge=1, le=20)


def create_router(app, engine, settings, logger, cache):
    router = APIRouter()

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
            raise HTTPException(
                exc.status_code, "Không thể xác thực truy cập AI"
            ) from exc

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

    @router.get("/health/live")
    def live():
        return {"status": "ok", "service": "ai"}

    @router.get("/health/ready")
    def ready():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            cache.ping()
        except Exception:
            return JSONResponse(
                {"status": "not_ready", "service": "ai"}, status_code=503
            )
        return {"status": "ready", "service": "ai"}

    @router.get(
        "/internal/v1/migration/state",
        dependencies=[Depends(private)],
        include_in_schema=False,
    )
    def migration_state():
        return {"writes_enabled": settings.writes_enabled}

    @router.post("/ai/chat", dependencies=[Depends(writes)])
    def ask(body: ChatRequest, user=Depends(current_user), db=Depends(db_session)):
        reader = ReadSession(app.state.read_http, settings)
        return chat_service.chat(db, user.user_id, body, cache, reader, settings,
                                 graph=app.state.knowledge_graph)

    @router.get("/ai/conversations", response_model=list[ConversationRead])
    def conversations(
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        user=Depends(current_user),
        db=Depends(db_session),
    ):
        return history.list_conversations(db, user.user_id, limit, offset)

    @router.get(
        "/ai/conversations/{conversation_id}", response_model=ConversationDetail
    )
    def conversation(
        conversation_id: UUID,
        limit: int = Query(100, ge=1, le=200),
        before_id: int | None = Query(None, gt=0),
        user=Depends(current_user),
        db=Depends(db_session),
    ):
        return history.read_conversation(
            db, user.user_id, conversation_id, limit, before_id
        )

    @router.delete(
        "/ai/conversations/{conversation_id}",
        status_code=204,
        dependencies=[Depends(writes)],
    )
    def delete_conversation(
        conversation_id: UUID, user=Depends(current_user), db=Depends(db_session)
    ):
        history.delete_conversation(db, user.user_id, conversation_id, cache)
        return Response(status_code=204)

    @router.get("/admin/documents")
    def document_list(
        q: str = Query("", max_length=100),
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        user=Depends(knowledge_user),
        db=Depends(db_session),
    ):
        stmt = select(KnowledgeDocument)
        if q:
            stmt = stmt.where(
                or_(
                    KnowledgeDocument.title.icontains(q, autoescape=True),
                    KnowledgeDocument.source_id.icontains(q, autoescape=True),
                )
            )
        total = db.exec(select(func.count()).select_from(stmt.subquery())).one()
        return {
            "items": db.exec(
                stmt.order_by(KnowledgeDocument.id.desc()).offset(offset).limit(limit)
            ).all(),
            "total": total,
        }

    @router.post("/admin/knowledge/search")
    def knowledge_search(body: KnowledgeSearch, user=Depends(knowledge_user), db=Depends(db_session)):
        from ..rag import retrieve
        from time import perf_counter
        started = perf_counter()
        try:
            sources = retrieve(db, body.question, body.limit, strategy=body.strategy, scope=body.scope,
                              embedding_url=settings.embedding_url, reranker_url=settings.reranker_url)
        except Exception:
            raise HTTPException(503, "Không chạy được cấu hình truy xuất; kiểm tra inference service")
        return dict(question=body.question, strategy=body.strategy, scope=body.scope, sources=sources,
                    latency_ms=round((perf_counter()-started)*1000, 2))

    @router.get("/admin/documents/{document_id}")
    def document(
        document_id: int, user=Depends(knowledge_user), db=Depends(db_session)
    ):
        return documents.document_detail(db, document_id)

    @router.post("/admin/documents", dependencies=[Depends(writes)])
    def document_write(
        body: DocumentWrite, user=Depends(knowledge_user), db=Depends(db_session)
    ):
        return documents.document_write(db, body, settings.graph_release_id if settings.graph_uri else "")

    @router.put(
        "/admin/documents/{document_id}/approval", dependencies=[Depends(writes)]
    )
    def approve(
        document_id: int,
        body: DocumentApproval,
        user=Depends(knowledge_user),
        db=Depends(db_session),
    ):
        return documents.document_approve(db, document_id, body, settings.graph_release_id if settings.graph_uri else "")

    @router.get("/admin/documents/{document_id}/revisions")
    def revisions(document_id: int, user=Depends(knowledge_user), db=Depends(db_session)):
        return knowledge_versions.revision_list(db, document_id)

    @router.post("/admin/documents/{document_id}/revisions", dependencies=[Depends(writes)])
    def stage_revision(document_id: int, body: DocumentRevisionWrite,
                       user=Depends(knowledge_user), db=Depends(db_session)):
        return knowledge_versions.stage(db, document_id, body, user.user_id)

    @router.get("/admin/documents/{document_id}/revisions/{revision_id}")
    def revision(document_id: int, revision_id: UUID, user=Depends(knowledge_user), db=Depends(db_session)):
        return knowledge_versions.revision_detail(db, document_id, revision_id)

    @router.put("/admin/documents/{document_id}/revisions/{revision_id}/publication", dependencies=[Depends(writes)])
    def publish_revision(document_id: int, revision_id: UUID, body: DocumentRevisionPublish,
                         user=Depends(knowledge_user), db=Depends(db_session)):
        return knowledge_versions.publish(db, document_id, revision_id, body, user.user_id, app.state.knowledge_graph)

    @router.delete("/admin/documents/{document_id}", dependencies=[Depends(writes)])
    def document_delete(
        document_id: int, user=Depends(knowledge_user), db=Depends(db_session)
    ):
        return documents.document_delete(db, document_id)

    return router
