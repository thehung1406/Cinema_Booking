from datetime import timedelta
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from sqlalchemy import func
from cinema_platform.events import OutboxRecord
from review_service.main import create_app
from review_service.models import Review, ReviewSentiment, utcnow
from review_service.worker import process_one

HEADERS = {"Authorization": "Bearer test-only"}
PREDICTOR = (lambda text: {"positive": .9, "neutral": .05, "negative": .05}, "test-fixture-model")


def client_for(store, settings, read=None, auth=None):
    state = {"user_id": 1, "role": "USER", "is_active": True, "permissions": []}
    def reads(request):
        if "/films/" in request.url.path:
            if request.url.path.endswith("/999"):
                return httpx.Response(404)
            return httpx.Response(200, json={"id": 1, "title": "Phim test", "image": None})
        if request.url.path.endswith("/candidates"):
            films = [] if request.url.params.get("theater_id") == "999" else [{"id": 1, "title": "Phim test", "image": None}]
            return httpx.Response(200, json=films)
        return httpx.Response(200, json=[r | {"author": f"User {r['user_id']}", "verified_purchase": True}
            for r in json.loads(request.content)["items"]])
    app = create_app(settings, engine=store, auth_transport=httpx.MockTransport(auth or (lambda request: httpx.Response(200, json=state))),
        read_transport=httpx.MockTransport(read or reads))
    return TestClient(app), state


def test_permissions_moderation_ownership_edit_delete_recreate(review_store, review_settings):
    client, state = client_for(review_store, review_settings)
    with client:
        assert client.post("/films/1/reviews", json={"content": "Phim rất hay"}).status_code == 401
        assert client.post("/films/999/reviews", headers=HEADERS, json={"content": "Phim rất hay"}).status_code == 404
        saved = client.post("/films/1/reviews", headers=HEADERS, json={"content": "Phim rất hay"})
        assert saved.status_code == 201 and saved.json()["verified_purchase"]
        rid = saved.json()["id"]
        assert saved.json()["moderation_status"] == "pending"
        assert client.get("/films/1/reviews").json() == []
        assert client.get("/films/1/reviews/mine", headers=HEADERS).json()["id"] == rid
        assert client.post("/films/1/reviews", headers=HEADERS, json={"content": "Bị trùng"}).status_code == 409
        body = {"content_version": 1, "status": "approved"}
        assert client.patch(f"/reviews/{rid}/moderation", headers=HEADERS, json=body).status_code == 403
        state["permissions"] = ["reviews.moderate"]
        assert len(client.get("/reviews/moderation/pending", headers=HEADERS).json()) == 1
        assert client.patch(f"/reviews/{rid}/moderation", headers=HEADERS, json=body).status_code == 200
        assert len(client.get("/films/1/reviews").json()) == 1
        state["user_id"] = 2
        assert client.get("/films/1/reviews/mine", headers=HEADERS).json() is None
        assert client.patch(f"/reviews/{rid}", headers=HEADERS, json={"content": "Sửa trái phép", "content_version": 1}).status_code == 403
        assert client.delete(f"/reviews/{rid}", headers=HEADERS).status_code == 403
        state["user_id"] = 1
        edited = client.patch(f"/reviews/{rid}", headers=HEADERS, json={"content": "Nội dung thay đổi", "content_version": 1})
        assert edited.status_code == 200 and edited.json()["content_version"] == 2 and edited.json()["moderation_status"] == "pending"
        assert client.patch(f"/reviews/{rid}/moderation", headers=HEADERS, json=body).status_code == 409
        assert client.post(f"/reviews/{rid}/retry", headers=HEADERS).status_code == 409
        assert client.delete(f"/reviews/{rid}", headers=HEADERS).status_code == 204
        assert client.get("/films/1/reviews/mine", headers=HEADERS).json() is None
        recreated = client.post("/films/1/reviews", headers=HEADERS, json={"content": "Viết đánh giá lại"})
        assert recreated.status_code == 201 and recreated.json()["id"] == rid and recreated.json()["content_version"] == 4
        state["permissions"] = []
        assert client.get("/reviews/moderation/pending", headers=HEADERS).status_code == 403
        state["is_active"] = False
        assert client.get("/films/1/reviews/mine", headers=HEADERS).status_code == 403
    with Session(review_store) as db:
        events = db.exec(select(OutboxRecord).order_by(OutboxRecord.aggregate_version)).all()
        assert [r.aggregate_version for r in events] == list(range(1, 6))
        assert all("content" not in r.payload["data"] and "user_id" not in r.payload["data"] for r in events)


def test_analysis_ranking_window_and_reporting_semantics(review_store, review_settings):
    review_settings.auto_approve = True
    review_settings.sentiment_min_reviews = 1
    client, state = client_for(review_store, review_settings)
    with client:
        rid = client.post("/films/1/reviews", headers=HEADERS, json={"content": "Bộ phim hay lắm"}).json()["id"]
        assert process_one(review_store, review_settings, PREDICTOR) == "succeeded"
        assert process_one(review_store, review_settings, PREDICTOR) is False
        summary = client.get("/films/1/sentiment-summary").json()
        assert summary["total"] == summary["positive"] == 1
        assert client.get("/films/positive-trending").json()[0]["film_id"] == 1
        assert client.get("/films/positive-trending?theater_id=999").json() == []
        private = {"X-Service-Key": review_settings.service_key}
        body = {"start_date": (utcnow()-timedelta(days=1)).date().isoformat(), "end_date": utcnow().date().isoformat()}
        assert client.post("/internal/v1/report-sentiments", json=body).status_code == 401
        report = client.post("/internal/v1/report-sentiments", json=body, headers=private).json()
        assert report == {"positive": 1, "neutral": 0, "negative": 0, "total": 1, "pending": 0, "coverage": 100}
        assert client.post("/internal/v1/report-sentiments", json=body | {"film_ids": []}, headers=private).json()["total"] == 0
        with Session(review_store) as db:
            review = db.get(Review, rid)
            review.updated_at = utcnow()-timedelta(days=40)
            db.commit()
        assert client.get("/films/1/sentiment-summary").json()["total"] == 0
        assert client.get("/films/1/sentiment-summary?window_days=60").json()["total"] == 1
        assert client.post("/internal/v1/report-sentiments", json=body, headers=private).json()["total"] == 0


@pytest.mark.parametrize("outage", ["read", "auth"])
def test_upstream_failure_and_freeze_do_not_create_review(review_store, review_settings, outage):
    def unavailable(request):
        raise httpx.ConnectError("isolated outage", request=request)
    client, state = client_for(review_store, review_settings, **{outage: unavailable})
    with client:
        assert client.post("/films/1/reviews", headers=HEADERS, json={"content": "Phim hay lắm"}).status_code == 503
    review_settings.writes_enabled = False
    client, _ = client_for(review_store, review_settings)
    with client:
        assert client.post("/films/1/reviews", headers=HEADERS, json={"content": "Phim hay lắm"}).status_code == 503
    with Session(review_store) as db:
        assert db.scalar(select(func.count()).select_from(Review)) == 0
        assert db.scalar(select(func.count()).select_from(OutboxRecord)) == 0
