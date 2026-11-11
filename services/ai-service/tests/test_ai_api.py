from datetime import timedelta
from uuid import UUID

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import delete, func, select, update
from sqlmodel import Session

from ai_service.main import create_app
from ai_service.models import AIConversation, AIMessage, utcnow
from ai_support import FakeCache


def client_for(store, settings, *, permissions=None, read=None, cache=None):
    state = {"user_id": 1, "role": "USER", "permissions": permissions or [], "is_active": True}
    def auth(request):
        return httpx.Response(200, json=state)
    def reads(request):
        import json
        body = json.loads(request.content)
        if request.url.path.endswith("/matches"):
            return httpx.Response(200, json={"film_id": [], "theater_id": []})
        if request.url.path.endswith("/context"):
            if body.get("showtime_id") == 999:
                return httpx.Response(422, json={"detail": "showtime_id không tồn tại"})
            return httpx.Response(200, json={"film_name": None, "theater_name": None})
        return httpx.Response(200, json=[{"id": "price:1", "title": "Standard", "text": "Suất 1: 75,000 VND.", "url": "/seat-selection/1", "kind": "live"}])
    app = create_app(settings, engine=store, cache=cache or FakeCache(), auth_transport=httpx.MockTransport(auth), read_transport=httpx.MockTransport(read or reads))
    return TestClient(app), state


HEADERS = {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize('message,intent', [('Mã suất 1 còn ghế nào?', 'get_seat_availability'), ('Giá vé mã suất 1?', 'get_ticket_prices')])
def test_explicit_live_fact_request_overrides_wrong_model_tool(ai_store, ai_settings, monkeypatch, message, intent):
    from ai_service.schemas import AssistantPlan
    from ai_service import llm
    ai_settings.llm_provider = 'ollama'
    monkeypatch.setattr(llm, 'plan', lambda *args: AssistantPlan(intent='search_films'))
    client, _ = client_for(ai_store, ai_settings)
    with client:
        response = client.post('/ai/chat', headers=HEADERS, json={'message': message})
        assert response.status_code == 200
        assert response.json()['tool'] == intent


def test_planner_timeout_leaves_time_for_direct_booking(ai_store, ai_settings, monkeypatch):
    from types import SimpleNamespace
    from ai_service import chat, llm, read_client

    elapsed = 0
    monkeypatch.setattr(chat, "monotonic", lambda: elapsed)
    monkeypatch.setattr(read_client, "time", SimpleNamespace(monotonic=lambda: elapsed))
    ai_settings.llm_provider = "ollama"
    ai_settings.llm_timeout_seconds = 20
    ai_settings.direct_reads_enabled = True

    def timeout(settings, *_):
        nonlocal elapsed
        elapsed += settings.llm_timeout_seconds
        raise httpx.ReadTimeout("Simulated slow model")

    def reads(request):
        if request.url.path.endswith("/options"):
            return httpx.Response(200, json={"items": []})
        assert request.url.path.endswith("/matches")
        return httpx.Response(200, json=[])

    monkeypatch.setattr(llm, "plan", timeout)
    client, _ = client_for(ai_store, ai_settings, read=reads)
    with client:
        response = client.post("/ai/chat", headers=HEADERS, json={"message": "Ngày mai muốn xem phim hài"})
    assert response.status_code == 200
    assert response.json()["status"] == "no_results"
    assert response.json()["mode"] == "model_unavailable"


def test_knowledge_inference_shares_one_budget(ai_store, ai_settings, monkeypatch):
    from ai_service import chat, llm
    from ai_service.schemas import AssistantPlan

    elapsed = 0
    monkeypatch.setattr(chat, "monotonic", lambda: elapsed)
    ai_settings.llm_provider = "ollama"
    ai_settings.llm_timeout_seconds = 20

    def plan(settings, *_):
        nonlocal elapsed
        elapsed += settings.llm_timeout_seconds
        return AssistantPlan(intent="knowledge")

    def answer(settings, *_):
        assert elapsed + settings.llm_timeout_seconds < 25
        return "Đoạn trích đã duyệt."

    monkeypatch.setattr(llm, "plan", plan)
    monkeypatch.setattr(llm, "grounded_answer", answer)
    monkeypatch.setattr(chat, "retrieve", lambda *args, **kwargs: [
        {"id": "doc:1", "text": "Đoạn trích đã duyệt.", "kind": "document"}
    ])
    client, _ = client_for(ai_store, ai_settings)
    with client:
        response = client.post("/ai/chat", headers=HEADERS, json={"message": "Thể loại điện ảnh là gì?"})
    assert response.status_code == 200
    assert response.json()["mode"] == "grounded_generation"


def test_recommendation_budget_followup_preserves_party_and_allows_topic_change(ai_store, ai_settings):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import json
    options = []
    def reads(request):
        if request.url.path.endswith('/options'):
            payload = json.loads(request.content)
            options.append(payload)
            items = [dict(showtime_id=1, sales_version=1, film_id=1, film_title="Phim hài",
                theater_id=1, theater_name="Rạp", room_name="Phòng 1", show_date=payload["show_date"],
                start_time="19:00:00", format="2D", available_seats=10, min_ticket_price=75000,
                minimum_total=150000, party_size=2, currency="VND", url="/seat-selection/1")
            ] if payload["budget_total"] == "250000" else []
            return httpx.Response(200, json={"items": items, "has_more": False})
        if request.url.path.endswith('/matches'):
            return httpx.Response(200, json={"film_id": [], "theater_id": []})
        return httpx.Response(200, json={"film_name": None, "theater_name": None})
    client, _ = client_for(ai_store, ai_settings, read=reads)
    with client:
        question = {"message": "Ngày mai muốn xem phim hài, hai người, dưới 250k"}
        first = client.post('/ai/chat', headers=HEADERS, json=question).json()
        assert first['missing_fields'] == ['budget_scope'] and not options
        second = client.post('/ai/chat', headers=HEADERS,
            json={"conversation_id": first['conversation_id'], "message": "Tổng cả nhóm"})
        assert second.status_code == 200 and len(second.json()['cards']) == 1
        assert options[-1]['party_size'] == 2 and options[-1]['budget_total'] == '250000'
        assert options[-1]['show_date'] == (datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date()+timedelta(days=1)).isoformat()
        refined = client.post('/ai/chat', headers=HEADERS,
            json={"conversation_id": first['conversation_id'], "message": "Tổng dưới 100k"})
        assert refined.status_code == 200 and refined.json()['status'] == 'no_results'
        assert options[-1]['party_size'] == 2 and options[-1]['budget_total'] == '100000'
        with Session(ai_store) as db:
            assert db.get(AIConversation, UUID(first['conversation_id'])).context['options'] == []
        policy = client.post('/ai/chat', headers=HEADERS,
            json={"conversation_id": first['conversation_id'], "message": "Chính sách hoàn tiền là gì?"})
        assert policy.status_code == 200 and policy.json()['status'] == 'no_evidence'
        assert len(options) == 2
        pending = client.post('/ai/chat', headers=HEADERS, json=question).json()
        changed = client.post('/ai/chat', headers=HEADERS,
            json={"conversation_id": pending['conversation_id'], "message": "Đặt hộ hai vé"}).json()
        assert changed['status'] == 'out_of_scope' and len(options) == 2


def test_history_context_pagination_owner_and_delete(ai_store, ai_settings):
    client, state = client_for(ai_store, ai_settings)
    with client:
        assert client.get("/ai/conversations").status_code == 401
        first = client.post("/ai/chat", headers=HEADERS, json={"message": "Gia ve?"})
        assert first.status_code == 200 and first.json()["status"] == "needs_clarification"
        cid = first.json()["conversation_id"]
        second = client.post("/ai/chat", headers=HEADERS, json={"message": "Ma suat 1", "conversation_id": cid})
        assert second.status_code == 200 and "75,000" in second.json()["answer"]
        detail = client.get(f"/ai/conversations/{cid}?limit=2", headers=HEADERS).json()
        assert detail["next_before_id"] and len(detail["messages"]) == 2
        older = client.get(f"/ai/conversations/{cid}?limit=2&before_id={detail['next_before_id']}", headers=HEADERS).json()
        assert older["next_before_id"] is None and len(older["messages"]) == 2
        state["user_id"] = 2
        assert client.get("/ai/conversations", headers=HEADERS).json() == []
        assert client.get(f"/ai/conversations/{cid}", headers=HEADERS).status_code == 404
        assert client.delete(f"/ai/conversations/{cid}", headers=HEADERS).status_code == 404
        state["user_id"] = 1
        assert client.delete(f"/ai/conversations/{cid}", headers=HEADERS).status_code == 204
        assert client.post("/ai/chat", headers=HEADERS, json={"message": "Tiếp tục", "conversation_id": cid}).status_code == 404
    with Session(ai_store) as db:
        assert db.scalar(select(func.count()).select_from(AIMessage)) == 0


def test_knowledge_permissions_approval_version_and_grounded_answer(ai_store, ai_settings):
    client, state = client_for(ai_store, ai_settings)
    body = {"source_id": "hold-policy", "title": "Chính sách giữ ghế", "version": "1", "source_url": "/booking",
            "effective_at": (utcnow() - timedelta(days=1)).isoformat(), "content": "Thời gian giữ ghế là 10 phút. Giữ ghế và thanh toán trong thời gian này."}
    with client:
        assert client.post("/admin/documents", headers=HEADERS, json=body).status_code == 403
        state["permissions"] = ["knowledge.manage"]
        saved = client.post("/admin/documents", headers=HEADERS, json=body)
        assert saved.status_code == 200 and not saved.json()["approved"]
        doc = saved.json()
        assert client.get("/admin/documents", headers=HEADERS).json()["total"] == 1
        approval = {"version": doc["version"], "expected_updated_at": doc["updated_at"], "approved": True}
        approved = client.put(f"/admin/documents/{doc['id']}/approval", headers=HEADERS, json=approval)
        assert approved.status_code == 200 and approved.json()["approved"]
        answer = client.post("/ai/chat", headers=HEADERS, json={"message": "Giữ ghế bao lâu?"}).json()
        assert "10 phút" in answer["answer"] and answer["sources"][0]["kind"] == "document"
        assert client.post("/admin/documents", headers=HEADERS, json=body | {"expected_updated_at": doc["updated_at"]}).status_code == 409
        new = client.post("/admin/documents", headers=HEADERS, json=body | {"version": "2", "expected_updated_at": approved.json()["updated_at"]})
        assert new.status_code == 200 and not new.json()["approved"]
        assert client.put(f"/admin/documents/{doc['id']}/approval", headers=HEADERS, json=approval).status_code == 409


@pytest.mark.parametrize("deleted", [False, True])
def test_concurrent_turn_cannot_overwrite_or_recreate_chat(ai_store, ai_settings, monkeypatch, deleted):
    from ai_service import chat
    client, state = client_for(ai_store, ai_settings)
    with client:
        cid = client.post("/ai/chat", headers=HEADERS, json={"message": "Xin chào"}).json()["conversation_id"]
        def concurrent(*args, **kwargs):
            with Session(ai_store) as db:
                if deleted:
                    db.execute(delete(AIConversation).where(AIConversation.id == UUID(cid)))
                else:
                    # Windows clocks can return the same instant for two quick writes.
                    # Make the simulated competing revision unambiguously different.
                    db.execute(update(AIConversation).where(AIConversation.id == UUID(cid)).values(updated_at=utcnow() + timedelta(seconds=1)))
                db.commit()
            return [], "retrieval_only"
        monkeypatch.setattr(chat, "select_evidence", concurrent)
        response = client.post("/ai/chat", headers=HEADERS, json={"message": "Cách đặt vé?", "conversation_id": cid})
        assert response.status_code == 409
    with Session(ai_store) as db:
        assert db.scalar(select(func.count()).select_from(AIMessage)) == (0 if deleted else 2)


def test_freeze_rate_limit_invalid_context_and_read_outage(ai_store, ai_settings):
    ai_settings.writes_enabled = False
    cache = FakeCache()
    client, state = client_for(ai_store, ai_settings, cache=cache)
    with client:
        assert client.post("/ai/chat", headers=HEADERS, json={"message": "Xin chào"}).status_code == 503
        ai_settings.writes_enabled = True
        invalid = client.post("/ai/chat", headers=HEADERS, json={"message": "Giá vé?", "context": {"showtime_id": 999}})
        assert invalid.status_code == 422
        cache.counts["ai:rate:1"] = ai_settings.requests_per_minute
        assert client.post("/ai/chat", headers=HEADERS, json={"message": "Xin chào"}).status_code == 429
    def timeout(request):
        raise httpx.ConnectError("business connection unavailable", request=request)
    client, _ = client_for(ai_store, ai_settings, read=timeout)
    with client:
        assert client.post("/ai/chat", headers=HEADERS, json={"message": "Giá vé?"}).status_code == 503
    with Session(ai_store) as db:
        assert db.scalar(select(func.count()).select_from(AIMessage)) == 0


@pytest.mark.parametrize("ids,mode", [(["doc:1"],"model_assisted"),(["invented"],"model_unavailable")])
def test_model_can_only_select_existing_evidence_never_replace_text_or_url(ai_settings, monkeypatch, ids, mode):
    from ai_service.chat import select_evidence
    original_client = httpx.Client
    evidence = [{"id": "doc:1", "title": "Chính sách", "text": "Nội dung đã duyệt", "url": "/booking", "kind": "document"}]
    ai_settings.model_url = "http://model.test"
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"evidence_ids": ids, "answer": "Giá giả", "url": "https://evil.test"}))
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original_client(transport=transport, **kwargs))
    selected, actual_mode = select_evidence("Câu hỏi", evidence, ai_settings)
    assert selected == evidence and actual_mode == mode


def test_failed_history_commit_cannot_leave_half_conversation(ai_store, ai_settings, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    cache = FakeCache()
    client, _ = client_for(ai_store, ai_settings, cache=cache)
    def fail(self):
        raise SQLAlchemyError("Injected commit failure")
    monkeypatch.setattr(Session, "commit", fail)
    with client:
        assert client.post("/ai/chat", headers=HEADERS, json={"message": "Xin chào"}).status_code == 503
    with Session(ai_store) as db:
        assert db.scalar(select(func.count()).select_from(AIConversation)) == 0
        assert db.scalar(select(func.count()).select_from(AIMessage)) == 0
    assert cache.values == {}
