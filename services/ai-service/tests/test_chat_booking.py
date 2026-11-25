import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from ai_service import llm
from ai_service.main import create_app
from ai_service.models import Base
from ai_service.chat import detect_intent
from fastapi.testclient import TestClient

from ai_support import FakeCache


HEADERS = {"Authorization": "Bearer customer-token"}
RESERVATION = "915167e4-6130-4ad0-826c-7922986d41da"
DEADLINE = "2030-04-01T18:20:00Z"


def test_booking_policy_takes_precedence_over_booking_request():
    assert detect_intent("Đặt vé rồi có được hoàn tiền không?") == "knowledge"
    assert detect_intent("Tôi đặt vé trên website như thế nào?") == "knowledge"
    assert detect_intent("Đặt hai vé phim hài tối nay") == "recommend"
    assert detect_intent("Tôi muốn đặt hôm nay hai vé") == "recommend"
    assert detect_intent("Đặt hộ tôi hai vé") == "out_of_scope"


def test_booking_policy_question_with_an_ordinal_uses_knowledge(client_factory):
    def owner(request):
        pytest.fail(f"Policy question tried to use a business read: {request.url.path}")

    with client_factory(owner) as client:
        response = client.post("/ai/chat", headers=HEADERS, json={"message": "Cách đặt vé suất đầu tiên?"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "no_evidence"


@pytest.fixture
def client_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def make(owner, **overrides):
        from ai_service.config import Settings

        settings = Settings(**(dict(database_url="sqlite://", redis_url="redis://localhost/0", writes_enabled=True,
                                    llm_provider="disabled", service_key="a" * 32) | overrides))
        auth = httpx.MockTransport(lambda _: httpx.Response(200, json={"user_id": 7, "role": "USER", "permissions": [], "is_active": True}))
        return TestClient(create_app(settings, engine=engine, cache=FakeCache(), auth_transport=auth,
                                     read_transport=httpx.MockTransport(owner)))

    yield make
    engine.dispose()


def test_booking_writes_preserve_customer_authorization_and_idempotency(client_factory):
    calls = []

    def owner(request):
        assert request.headers["authorization"] == "Bearer customer-token"
        payload = json.loads(request.content)
        calls.append(request.url.path)
        if request.url.path == "/seats/hold":
            assert payload == {"showtime_id": 11, "seat_ids": [4]}
            return httpx.Response(200, json=[dict(seat_id=4, seat_name="A5", status="HOLD", reservation_id=RESERVATION, hold_expired_at=DEADLINE)])
        if request.url.path == "/bookings":
            assert request.headers["idempotency-key"] == "same-confirmation"
            assert payload["userId"] == 7 and payload["paymentMethod"] == "Online"
            assert payload["foodItems"] == [{"food_item_id": 3, "quantity": 2}]
            return httpx.Response(201, json={"bookingId": 77, "expiresAt": DEADLINE, "userId": 7})
        assert request.url.path == "/seats/release" and payload["reservation_id"] == RESERVATION
        return httpx.Response(200, json={"released_seats": 1, "message": "Đã hủy giữ 1 ghế"})

    with client_factory(owner) as client:
        body = {"showtime_id": 11, "seat_ids": [4]}
        assert client.post("/ai/booking/hold", json=body).status_code == 401
        assert client.post("/ai/booking/hold", headers=HEADERS, json=body | {"seat_ids": [4, 4]}).status_code == 422
        held = client.post("/ai/booking/hold", headers=HEADERS, json=body)
        assert held.status_code == 200 and held.json()[0]["reservation_id"] == RESERVATION
        assert client.post("/ai/booking/release", headers=HEADERS, json=body | {"reservation_id": RESERVATION}).status_code == 200
        checkout = {"showtime_id": 11, "reservation_id": RESERVATION, "total_amount": "190000.00",
                    "seats": [{"seat_id": 4, "price": "90000.00"}], "food_items": [{"food_item_id": 3, "quantity": 2}]}
        headers = HEADERS | {"Idempotency-Key": "same-confirmation"}
        assert client.post("/ai/booking/checkout", headers=headers, json=checkout | {"userId": 42}).status_code == 422
        for _ in range(2):
            created = client.post("/ai/booking/checkout", headers=headers, json=checkout)
            assert created.status_code == 201 and created.json() == {"bookingId": 77, "expiresAt": DEADLINE}
    assert calls == ["/seats/hold", "/seats/release", "/bookings", "/bookings"]


@pytest.mark.parametrize("question,context,status,tool,theater,showtime", [
    ("Suất đầu tiên ở Rạp mới giá vé bao nhiêu?", {}, "ok", "get_ticket_prices", 2, 21),
    ("Suất thứ hai còn ghế nào ở Rạp mới?", {}, "ok", "get_seat_availability", 2, 20),
    ("Suất đầu ở Rạp trống giá vé bao nhiêu?", {}, "no_results", "get_ticket_prices", 3, None),
    ("Suất đầu ở Rạp mới giá vé bao nhiêu?", {"show_date": None}, "needs_clarification", "get_ticket_prices", 2, None),
    ("Suất đầu tại Galaxy Nguyễn Du giá vé bao nhiêu?", {}, "needs_clarification", "get_ticket_prices", None, None),
])
def test_ordinal_lookup_uses_the_new_theater(client_factory, question, context, status, tool, theater, showtime):
    day = (date.today() + timedelta(days=3)).isoformat()
    calls = []

    def owner(request):
        path = request.url.path
        payload = json.loads(request.content)
        if path.endswith("/matches"):
            return httpx.Response(200, json={"film_id": [], "theater_id": [
                {"id": id, "name": name} for id, name in [(2, "Rạp mới"), (3, "Rạp trống"),
                                                          (4, "Galaxy"), (5, "Galaxy Nguyễn Du")]
                if name in payload["message"]
            ]})
        if path.endswith("/context"):
            return httpx.Response(200, json={"film_name": "Phim A", "theater_name": None})
        assert path.endswith("/tool")
        call = payload["call"]
        name, scope = call["name"], call["context"]
        calls.append((name, scope["theater_id"], scope["showtime_id"]))
        ids = {1: [11], 2: [21, 20], 3: []}[scope["theater_id"]] if name == "get_showtimes" else [scope["showtime_id"]]
        return httpx.Response(200, json=[dict(
            id=f"{'showtime' if name == 'get_showtimes' else 'detail'}:{id}", title=f"Suất {id}",
            text=f"Thông tin suất {id}", url=f"/seat-selection/{id}", kind="live",
        ) for id in ids])

    with client_factory(owner) as client:
        first = client.post("/ai/chat", headers=HEADERS, json={
            "message": "Lịch chiếu?", "context": {"film_id": 1, "theater_id": 1, "show_date": day},
        }).json()
        response = client.post("/ai/chat", headers=HEADERS, json={
            "message": question, "conversation_id": first["conversation_id"], "context": context,
        })
        followup_message = "Suất thứ hai còn ghế nào?" if showtime == 21 else day if context else None
        if followup_message:
            followup = client.post("/ai/chat", headers=HEADERS, json={
                "message": followup_message, "conversation_id": first["conversation_id"],
            })
    assert response.status_code == 200, response.text
    result = response.json()
    assert (result["status"], result["tool"]) == (status, tool)
    assert (result["context"]["theater_id"], result["context"]["showtime_id"]) == (theater, showtime)
    expected_calls = [("get_showtimes", 1, None)]
    if status == "needs_clarification":
        assert result["missing_fields"] == ["theater_id" if theater is None else "show_date"]
    else:
        expected_calls.append(("get_showtimes", theater, None))
    if showtime:
        expected_calls.append((tool, theater, showtime))
        assert result["links"][0]["url"] == f"/seat-selection/{showtime}"
    else:
        assert result["links"] == []
    if followup_message:
        assert followup.status_code == 200, followup.text
        next_turn = followup.json()
        assert next_turn["status"] == "ok"
        if showtime == 21:
            assert next_turn["links"][0]["url"] == "/seat-selection/20"
            expected_calls.append(("get_seat_availability", 2, 20))
        else:
            assert next_turn["links"][0]["url"] == "/seat-selection/21"
            expected_calls.extend([("get_showtimes", 2, None), ("get_ticket_prices", 2, 21)])
    assert calls == expected_calls


def test_ordinal_schedule_lookup_can_be_retried_after_owner_failure(client_factory):
    scope = {"film_id": 1, "theater_id": 2, "show_date": (date.today() + timedelta(days=3)).isoformat()}
    schedules = 0

    def owner(request):
        nonlocal schedules
        path = request.url.path
        if path.endswith("/matches"):
            return httpx.Response(200, json={"film_id": [], "theater_id": []})
        if path.endswith("/context"):
            return httpx.Response(200, json={"film_name": "Phim A", "theater_name": "Rạp mới"})
        name = json.loads(request.content)["call"]["name"]
        if name == "get_showtimes":
            schedules += 1
            if schedules == 1:
                return httpx.Response(503)
        return httpx.Response(200, json=[dict(
            id="showtime:21" if name == "get_showtimes" else "price:21",
            title="Suất 21", text="Suất 21", url="/seat-selection/21", kind="live",
        )])

    with client_factory(owner) as client:
        first = client.post("/ai/chat", headers=HEADERS, json={"message": "Cách đặt vé?"}).json()
        query = {"message": "Giá vé suất đầu tiên?", "conversation_id": first["conversation_id"], "context": scope}
        failed = client.post("/ai/chat", headers=HEADERS, json=query)
        recovered = client.post("/ai/chat", headers=HEADERS, json=query)
    assert failed.status_code == 503
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["links"][0]["url"] == "/seat-selection/21"
    assert schedules == 2


def test_reset_filters_clears_saved_selection_without_losing_history(client_factory):
    def owner(request):
        if request.url.path.endswith("/matches"):
            return httpx.Response(200, json={"film_id": [], "theater_id": []})
        if request.url.path.endswith("/context"):
            return httpx.Response(200, json={"film_name": None, "theater_name": None})
        assert json.loads(request.content)["call"]["name"] == "get_showtimes"
        return httpx.Response(200, json=[dict(id="showtime:11", title="Suất 11", text="Suất 11",
                                             url="/seat-selection/11", kind="live")])

    with client_factory(owner) as client:
        first = client.post("/ai/chat", headers=HEADERS, json={"message": "Lịch chiếu?", "context": {
            "film_id": 1, "theater_id": 1, "show_date": (date.today() + timedelta(days=3)).isoformat(),
            "genre": "Hài", "party_size": 2, "budget_amount": "200000", "budget_scope": "total",
        }}).json()
        conversation_id = first["conversation_id"]
        response = client.post("/ai/chat", headers=HEADERS, json={
            "message": "Cách đặt vé?", "conversation_id": conversation_id,
            "reset_filters": True, "context": {"theater_id": 2},
        })
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["conversation_id"] == conversation_id and result["showtime_options"] is True
        assert {key: result["context"][key] for key in (
            "film_id", "theater_id", "show_date", "showtime_id", "genre", "party_size", "budget_amount",
        )} == {"film_id": None, "theater_id": 2, "show_date": None, "showtime_id": None,
               "genre": "", "party_size": 1, "budget_amount": None}
        missing = client.post("/ai/chat", headers=HEADERS, json={
            "message": "Giá vé suất đầu tiên?", "conversation_id": conversation_id,
        })
        assert missing.status_code == 422, missing.text
        history = client.get(f"/ai/conversations/{conversation_id}", headers=HEADERS).json()
    assert history["context"] == result["context"]
    assert [m["content"] for m in history["messages"] if m["role"] == "user"] == ["Lịch chiếu?", "Cách đặt vé?"]


@pytest.mark.parametrize("question,provider,day_offset,cutoff,genre,party,ids", [
    ("Tối mai phim nào chiếu sau 19 giờ?", "disabled", 1, "19:00:00", "", 1, [12]),
    ("Tối mai phim nào chiếu sau 19h?", "disabled", 1, "19:00:00", "", 1, [12]),
    ("Tối nay có phim hài nào còn suất chiếu cho hai người?", "disabled", 0, "18:00:00", "Hài", 2, [11, 12]),
    ("Tối nay có phim hài nào còn suất chiếu cho hai người?", "ollama", 0, "18:00:00", "Hài", 2, [11, 12]),
])
def test_film_discovery_uses_explicit_filters_when_the_model_is_unavailable(
        client_factory, monkeypatch, question, provider, day_offset, cutoff, genre, party, ids):
    day = (datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date() + timedelta(days=day_offset)).isoformat()
    queries = []

    def timeout(*args):
        raise TimeoutError("Planner timed out")

    def owner(request):
        path = request.url.path
        if path.endswith("/matches"):
            return httpx.Response(200, json=[])
        if path.endswith("/candidates"):
            return httpx.Response(200, json=[1])
        if path.endswith("/films/batch"):
            return httpx.Response(200, json=[{"id": 1, "title": "Phim chỉ có suất 18:30"}])
        assert path.endswith("/options")
        query = json.loads(request.content)
        queries.append({field: query[field] for field in ("show_date", "start_after", "genre", "party_size")})
        return httpx.Response(200, json={"items": [dict(
            showtime_id=id, sales_version=1, film_id=id - 10, film_title=f"Phim {id}", theater_id=1,
            theater_name="Rạp A", room_name="Phòng A", show_date=day, start_time=start,
            format="2D", available_seats=4, min_ticket_price=90000, minimum_total=party * 90000,
            party_size=party, currency="VND", url=f"/seat-selection/{id}",
        ) for id, start in [(11, "18:30:00"), (12, "19:15:00")] if start >= query["start_after"]]})

    monkeypatch.setattr(llm, "plan", timeout)
    with client_factory(owner, llm_provider=provider, direct_reads_enabled=True) as client:
        response = client.post("/ai/chat", headers=HEADERS, json={"message": question})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "ok"
    assert [card["showtime_id"] for card in result["cards"]] == ids
    assert queries == [dict(show_date=day, start_after=cutoff, genre=genre, party_size=party)]


@pytest.mark.parametrize("conditional", [False, True])
def test_ordinal_followups_use_the_latest_showtime_lookup(client_factory, monkeypatch, conditional):
    from ai_service import llm, react_lookup
    from ai_service.schemas import AssistantPlan

    day = (date.today() + timedelta(days=3)).isoformat()
    price_checks = []

    def evidence(id, url):
        return dict(id=id, url=url, kind="live", title=id, text=id)

    def owner(request):
        path = request.url.path
        payload = json.loads(request.content) if request.content else {}
        if path.endswith("/matches"):
            return httpx.Response(200, json={"film_id": [
                {"id": id, "name": name} for id, name in [(1, "Phim A"), (2, "Phim B")]
                if name in payload["message"]
            ], "theater_id": []})
        if path.endswith("/context"):
            return httpx.Response(200, json={"film_name": None, "theater_name": None})
        if path.endswith("/options"):
            assert payload["film_id"] == 1
            return httpx.Response(200, json={"items": [dict(
                showtime_id=id, sales_version=1, film_id=1, film_title="Phim A", theater_id=1,
                theater_name="Rạp X", room_name="Phòng X", show_date=day, start_time="19:00:00",
                format="2D", available_seats=4, min_ticket_price=90000, minimum_total=180000,
                party_size=2, currency="VND", url=f"/seat-selection/{id}",
            ) for id in (20, 21, 22)]})
        if path.endswith("/available-count"):
            return httpx.Response(200, json={"showtime_id": 31, "available_seats": 4})
        assert path.endswith("/tool")
        call = payload["call"]
        assert call["context"]["film_id"] == 2
        if call["name"] == "get_showtimes":
            return httpx.Response(200, json=[evidence(f"showtime:{id}", f"/seat-selection/{id}")
                                             for id in (31, 29)])
        assert call["name"] == "get_ticket_prices"
        showtime_id = call["context"]["showtime_id"]
        price_checks.append(showtime_id)
        return httpx.Response(200, json=[evidence("price:1", f"/seat-selection/{showtime_id}")])

    actions = iter([
        llm.FunctionCall("get_showtimes", {}, []),
        llm.FunctionCall("get_seat_availability", {"showtime_id": 31}, []),
        llm.FunctionCall("get_ticket_prices", {"showtime_id": 31}, []),
    ])
    monkeypatch.setattr(react_lookup, "function_step", lambda *args: next(actions))
    monkeypatch.setattr(llm, "plan", lambda *args: AssistantPlan(intent="get_ticket_prices"))
    with client_factory(owner, llm_provider="ollama" if conditional else "disabled", direct_reads_enabled=False) as client:
        def ask(message, **fields):
            return client.post("/ai/chat", headers=HEADERS, json={"message": message, **fields})

        first = ask("Đặt hai vé Phim A", context={"theater_id": 1, "show_date": day})
        assert first.status_code == 200, first.text
        assert [card["showtime_id"] for card in first.json()["cards"]] == [20, 21, 22]
        turn = {"conversation_id": first.json()["conversation_id"]}
        question = "Lịch chiếu Phim B?"
        if conditional:
            question += " Nếu suất đầu còn đủ hai ghế thì báo giá. Nếu không đủ thì kiểm tra suất tiếp theo."
        lookup = ask(question, **turn)
        assert lookup.status_code == 200, lookup.text
        assert lookup.json()["tool"] == ("react_lookup" if conditional else "get_showtimes")
        assert lookup.json()["showtime_options"] is True
        missing = ask("Giá vé suất thứ ba?", **turn)
        assert missing.status_code == 422, missing.text
        selected = ask("Giá vé suất thứ hai?", **turn)
        assert selected.status_code == 200, selected.text
        assert selected.json()["context"]["showtime_id"] == 29
        assert price_checks == ([31, 29] if conditional else [29])


@pytest.mark.parametrize("stage", ["AWAITING_PAYMENT", "PROCESSING", "REQUIRES_REVIEW", "FAILED", "ISSUED", None])
def test_personal_order_summary_is_fresh_and_omitted_from_history(client_factory, stage):
    def owner(request):
        assert request.headers["authorization"] == "Bearer customer-token"
        if request.url.path == "/bookings":
            assert request.url.params["limit"] == "1"
            return httpx.Response(200, json=[{"bookingId": 77, "userId": 7, "filmTitle": "Phim riêng tư",
                                             "bookingStatus": "PENDING", "totalAmount": 170000, "seats": [{"seat_id": 4}]}])
        assert request.url.path == "/payment/status/77"
        if stage is None:
            return httpx.Response(503)
        return httpx.Response(200, json={"booking_id": 77, "fulfillment_status": stage})

    with client_factory(owner) as client:
        response = client.post("/ai/chat", headers=HEADERS, json={"message": "Cho tôi xem vé vừa mua"})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["tool"] == "get_my_booking"
        assert data["booking"]["booking_id"] == 77 and data["booking"]["payment_stage"] == (stage or "UNKNOWN")
        assert data["booking"]["ticket_url"] == ("/payment-result?bookingId=77" if stage == "ISSUED" else None)
        history = client.get(f"/ai/conversations/{data['conversation_id']}", headers=HEADERS)
        assert history.status_code == 200 and "Phim riêng tư" not in history.text and "ticket_url" not in history.text


@pytest.mark.parametrize("code", [403, 404])
def test_other_customers_orders_are_indistinguishable_from_missing_orders(client_factory, code):
    def owner(request):
        assert request.url.path == "/bookings/123"
        return httpx.Response(code)

    with client_factory(owner) as client:
        lookup = client.post("/ai/chat", headers=HEADERS, json={"message": "Đơn #123 thế nào?"}).json()
        assert lookup["status"] == "no_results"
        assert lookup["answer"] == "Không tìm thấy đơn trong tài khoản của bạn."
        assert "booking" not in lookup


@pytest.mark.parametrize('message', ['Trạng thái booking #123 của mình?', 'Tra mã booking 123'])
def test_personal_lookup_uses_the_requested_booking_id(client_factory, message, monkeypatch):
    from ai_service.schemas import AssistantPlan

    def owner(request):
        assert request.headers['authorization'] == 'Bearer customer-token'
        if request.url.path == '/bookings/123':
            return httpx.Response(200, json={
                'bookingId': 123, 'userId': 7, 'filmTitle': 'Phim kiểm thử',
                'bookingStatus': 'PENDING', 'totalAmount': 170000, 'seats': [],
            })
        assert request.url.path == '/payment/status/123'
        return httpx.Response(200, json={'booking_id': 123, 'fulfillment_status': 'ISSUED'})

    monkeypatch.setattr(llm, 'plan', lambda *args, **kwargs: AssistantPlan(intent='get_my_booking'))
    with client_factory(owner, llm_provider='openai', openai_api_key='test-key') as client:
        result = client.post('/ai/chat', headers=HEADERS, json={'message': message})
    assert result.status_code == 200, result.text
    assert result.json()['booking']['booking_id'] == 123


@pytest.mark.parametrize('message', [
    'Tra booking #0 của mình', 'Tra booking #ABC', 'Tra mã booking',
    'Tra booking #123 và #456', 'Tra đơn 123 với booking #456',
    'Tra booking #123-456', 'Tra booking #1234567890123456789',
    'Tra #456 và booking #123', 'Tra booking #123; 456',
])
def test_invalid_or_multiple_booking_ids_require_clarification(client_factory, message, monkeypatch):
    from ai_service.schemas import AssistantPlan

    requests = []

    def owner(request):
        requests.append(request.url.path)
        return httpx.Response(404)

    monkeypatch.setattr(llm, 'plan', lambda *args, **kwargs: AssistantPlan(intent='get_my_booking'))
    with client_factory(owner, llm_provider='openai', openai_api_key='test-key') as client:
        result = client.post('/ai/chat', headers=HEADERS, json={'message': message})
    assert result.status_code == 200, result.text
    assert requests == []
    assert result.json()['status'] == 'needs_clarification'
    assert 'booking' not in result.json()
