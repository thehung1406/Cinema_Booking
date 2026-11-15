import json
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

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
