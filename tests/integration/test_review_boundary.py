import sys
from datetime import timedelta
from pathlib import Path
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from sqlalchemy import func

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend/tests"))
sys.path.insert(0, str(ROOT / "services/review-service/tests"))
from test_normalized_schema import pg, catalog  # noqa: E402,F401
from review_support import review_store  # noqa: E402,F401
from review_service.main import create_app  # noqa: E402
from review_service.config import Settings as ReviewSettings  # noqa: E402
from review_service.worker import process_one  # noqa: E402
from review_service.models import Review as OwnReview, ReviewSentiment as OwnSentiment  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import get_session  # noqa: E402
from app.models import Review, ReviewSentiment, Permission, RolePermission  # noqa: E402
from app.utils.dependencies import redis_client  # noqa: E402
from app.utils.security import create_access_token  # noqa: E402
from main import app as monolith  # noqa: E402


def test_real_auth_read_facade_ai_ranking_and_admin_report_use_review_owner(pg, catalog, review_store, monkeypatch):
    from app.services import review_remote
    from app.services.review_service import positive_films
    from app.repositories.admin_repo import report
    from app.schemas.admin import ReportFilters
    monkeypatch.setattr(settings, "REVIEW_STORAGE_OWNER", "service")
    monkeypatch.setattr(redis_client, "get", lambda key: None)
    saved = dict(monolith.dependency_overrides)
    monolith.dependency_overrides[get_session] = lambda: pg
    user = catalog["user"]
    token = create_access_token({"sub": str(user.id), "role": "ADMIN"})
    config = ReviewSettings(writes_enabled=True, auto_approve=True, sentiment_min_reviews=1)
    paths = []
    try:
        with TestClient(monolith) as backend:
            def business(request):
                paths.append(request.url.path)
                reply = backend.request(request.method, request.url.raw_path.decode(), headers=dict(request.headers), content=request.content)
                return httpx.Response(reply.status_code, json=reply.json())
            app = create_app(config, engine=review_store, auth_transport=httpx.MockTransport(business), read_transport=httpx.MockTransport(business))
            with TestClient(app) as client:
                headers = {"Authorization": "Bearer " + token}
                saved_review = client.post(f"/films/{catalog['film'].id}/reviews", headers=headers, json={"content": "Phim rất hay, nên xem"})
                assert saved_review.status_code == 201 and saved_review.json()["author"] == user.username
                rid = saved_review.json()["id"]
                assert client.patch(f"/reviews/{rid}/moderation", headers=headers, json={"content_version": 1, "status": "rejected"}).status_code == 403
                assert process_one(review_store, config, (lambda text: {"positive": .9, "negative": .05, "neutral": .05}, "boundary-test-model")) == "succeeded"
                def remote(method, path, **kwargs):
                    reply = client.request(method, "/internal/v1/" + path, headers={"X-Service-Key": config.service_key}, **kwargs)
                    reply.raise_for_status()
                    return reply.json()
                monkeypatch.setattr(review_remote, "request", remote)
                # Preserve the enclosing rollback-only catalog fixture across read-RPC rollbacks.
                monkeypatch.setattr(pg, "rollback", lambda: None)
                # Both source callers must use HTTP and must not use source Review rows.
                ranked = positive_films(pg)
                assert ranked[0]["film_id"] == catalog["film"].id
                assert backend.post("/internal/v1/ai-read/tool", headers={"X-Service-Key": settings.INTERNAL_SERVICE_KEY}, json={
                    "call": {"name": "get_positive_films", "context": {"theater_id": catalog["theater"].id, "show_date": catalog["show"].show_date.isoformat()}}, "evening": False}).status_code == 200
                today = catalog["show"].show_date
                result = report(pg, ReportFilters(start_date=today-timedelta(days=7), end_date=today))
                assert result["sentiments"]["positive"] == 1 and result["sentiments"]["total"] == 1
                assert pg.exec(select(Review)).all() == [] and pg.exec(select(ReviewSentiment)).all() == []
                assert backend.get("/films/positive-trending").status_code == 410
            assert "/internal/v1/auth/introspect" in paths and "/internal/v1/review-read/candidates" in paths
    finally:
        monolith.dependency_overrides.clear()
        monolith.dependency_overrides.update(saved)


@pytest.mark.parametrize("owner,status", [("maintenance",503),("service",410)])
def test_old_review_writers_and_inference_are_fenced(pg, monkeypatch, owner, status):
    from app.services.review_service import create_review
    from app.services.sentiment_service import process_review
    monkeypatch.setattr(settings, "REVIEW_STORAGE_OWNER", owner)
    for action in [lambda: create_review(pg, 1, 1, "Không được ghi cũ"), lambda: process_review(pg, 1, 1)]:
        with pytest.raises(HTTPException) as blocked:
            action()
        assert blocked.value.status_code == status


def test_review_connection_outage_fails_closed_for_ranking_and_report_without_legacy_reads(pg, monkeypatch):
    from datetime import date
    from sqlalchemy import event
    from app.services import review_remote
    from app.services.review_service import positive_films
    from app.repositories.admin_repo import report
    from app.schemas.admin import ReportFilters
    monkeypatch.setattr(settings, "REVIEW_STORAGE_OWNER", "service")
    original = httpx.Client
    def unavailable(request):
        raise httpx.ConnectError("isolated Review outage", request=request)
    monkeypatch.setattr(review_remote.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(unavailable), **kwargs))
    statements = []
    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(" ".join(statement.lower().split()))
    connection = pg.get_bind()
    event.listen(connection, "before_cursor_execute", capture)
    try:
        for action in [lambda: positive_films(pg), lambda: report(pg, ReportFilters(start_date=date.today(), end_date=date.today()))]:
            with pytest.raises(HTTPException) as failed:
                action()
            assert failed.value.status_code == 503
        assert not any("from reviews" in s or "join review_sentiments" in s for s in statements)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
