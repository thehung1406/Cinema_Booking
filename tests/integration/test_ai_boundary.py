from pathlib import Path
import sys

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlmodel import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend/tests"))
sys.path.insert(0, str(ROOT / "services/ai-service/tests"))
from test_normalized_schema import pg, catalog  # noqa: E402,F401
from ai_support import ai_store, FakeCache  # noqa: E402,F401
from ai_service.config import Settings as AISettings  # noqa: E402
from ai_service.main import create_app  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import get_session  # noqa: E402
from app.utils.dependencies import redis_client  # noqa: E402
from app.utils.security import create_access_token  # noqa: E402
from app.models import AIConversation as LegacyConversation, AIMessage as LegacyMessage  # noqa: E402
from main import app as monolith  # noqa: E402


def test_extracted_ai_uses_real_private_identity_and_read_only_business_apis(pg, catalog, ai_store, monkeypatch):
    monkeypatch.setattr(settings, "AI_STORAGE_OWNER", "service")
    monkeypatch.setattr(redis_client, "get", lambda key: None)
    saved = dict(monolith.dependency_overrides)
    monolith.dependency_overrides[get_session] = lambda: pg
    token = create_access_token({"sub": str(catalog["user"].id), "role": "USER"})
    try:
        with TestClient(monolith) as backend:
            paths = []
            def business_http(request):
                paths.append(request.url.path)
                reply = backend.request(request.method, request.url.path, headers=dict(request.headers), content=request.content)
                return httpx.Response(reply.status_code, json=reply.json())
            config = AISettings(writes_enabled=True)
            ai = create_app(config, engine=ai_store, cache=FakeCache(), auth_transport=httpx.MockTransport(business_http), read_transport=httpx.MockTransport(business_http))
            with TestClient(ai) as client:
                headers = {"Authorization": "Bearer " + token}
                result = client.post("/ai/chat", headers=headers, json={"message": "Giá vé?", "context": {"showtime_id": catalog["show"].id}})
                assert result.status_code == 200 and "75,000" in result.json()["answer"]
                assert client.get("/ai/conversations", headers=headers).json()[0]["id"] == result.json()["conversation_id"]
                assert client.post("/admin/documents", headers=headers, json={}).status_code == 403
            assert {"/internal/v1/auth/introspect", "/internal/v1/ai-read/matches", "/internal/v1/ai-read/context", "/internal/v1/ai-read/tool"} <= set(paths)
            assert pg.exec(select(LegacyConversation)).all() == []
            assert pg.exec(select(LegacyMessage)).all() == []
            assert backend.post("/ai/chat", headers={"Authorization": "Bearer " + token}, json={"message": "Không được ghi cũ"}).status_code == 410
    finally:
        monolith.dependency_overrides.clear()
        monolith.dependency_overrides.update(saved)


@pytest.mark.parametrize("owner,status", [("maintenance",503),("service",410)])
def test_legacy_ai_direct_writers_are_disabled_after_freeze(pg, monkeypatch, owner, status):
    from app.services.chat_service import chat
    from app.services.rag_service import upsert_document
    from app.schemas.ai import ChatRequest
    from fastapi import HTTPException
    monkeypatch.setattr(settings, "AI_STORAGE_OWNER", owner)
    with pytest.raises(HTTPException) as blocked:
        chat(pg, 1, ChatRequest(message="Xin chào"))
    assert blocked.value.status_code == status
    with pytest.raises(HTTPException) as blocked:
        upsert_document(pg, {})
    assert blocked.value.status_code == status
