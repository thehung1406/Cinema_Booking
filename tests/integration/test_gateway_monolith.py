"""Real monolith routers through the gateway, isolated PostgreSQL transactions.

The existing schema fixtures roll back application commits. VNPay/SMTP are not called.
Run via compose.migration-tests.yml, which supplies only dedicated test credentials.
"""

from contextlib import contextmanager, nullcontext
import hashlib
import hmac
from pathlib import Path
import sys
from urllib.parse import urlencode, quote_plus

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend/tests"))
from test_normalized_schema import pg, catalog, provider, provider_params  # noqa: E402,F401
from main import app as monolith  # noqa: E402
from app.core.database import get_session  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.models import Ticket  # noqa: E402
from app.repositories.payment_repo import PaymentRepository  # noqa: E402
from app.utils.dependencies import get_current_user, get_optional_current_user  # noqa: E402
from gateway.app.config import GatewaySettings  # noqa: E402
from gateway.app.main import create_app  # noqa: E402


@contextmanager
def proxied(pg, user):
    saved = dict(monolith.dependency_overrides)
    monolith.dependency_overrides[get_session] = lambda: pg
    monolith.dependency_overrides[get_current_user] = lambda: user
    monolith.dependency_overrides[get_optional_current_user] = lambda: user
    gateway = create_app(
        GatewaySettings(monolith_url="http://monolith:8000", _env_file=None),
        transport=httpx.ASGITransport(app=monolith),
    )
    try:
        with TestClient(gateway, follow_redirects=False) as client:
            yield client
    finally:
        monolith.dependency_overrides.clear()
        monolith.dependency_overrides.update(saved)


def test_film_food_auth_and_admin_permissions_keep_their_contract(pg, catalog):
    with proxied(pg, catalog["user"]) as client:
        film = client.get(f"/api/films/{catalog['film'].id}")
        assert film.status_code == 200 and film.json()["title"] == catalog["film"].title
        assert client.get("/api/food-items").status_code == 200
        profile = client.get("/api/auth/me")
        assert profile.status_code == 200 and profile.json()["id"] == catalog["user"].id
        assert "password" not in profile.json()
        assert client.get("/api/admin/films", headers={"X-Role": "ADMIN"}).status_code == 403
        assert client.get("/api/films/positive-trending").status_code == 200
        assert client.get("/api/ai/conversations").status_code == 200


def test_actual_vnpay_ipn_duplicate_callback_issues_one_ticket(pg, catalog, provider):
    attempt = PaymentRepository.create_attempt(pg, catalog["booking"])
    params = provider_params(attempt)
    with proxied(pg, catalog["user"]) as client:
        for _ in range(2):
            result = client.get("/api/payment/vnpay-ipn?" + urlencode(params))
            assert result.status_code == 200
            assert result.json()["RspCode"] in {"00", "02"}
        detail = client.get(f"/api/bookings/{catalog['booking'].id}")
        assert detail.status_code == 200
        assert detail.json()["paymentStatus"] == "PAID"
        assert detail.json()["bookingStatus"] == "CONFIRMED"
        tickets = client.get(f"/api/tickets/booking/{catalog['booking'].id}")
        assert tickets.status_code == 200 and len(tickets.json()) == 1
    assert len(pg.exec(select(Ticket).where(Ticket.booking_detail_id == catalog["detail"].id)).all()) == 1


def test_booking_validation_and_ownership_are_not_bypassed(pg, catalog):
    with proxied(pg, catalog["user"]) as client:
        assert client.post("/api/bookings", json={}).status_code == 422
        assert client.post("/api/bookings", json={
            "userId": catalog["user"].id + 10000,
            "showtimeId": catalog["show"].id,
            "totalAmount": 75000,
            "paymentMethod": "VNPAY",
            "seats": [{"seat_id": catalog["seat"].id, "price": 75000}],
        }).status_code == 403


@pytest.mark.parametrize("notification_transport", ["legacy", "events"])
def test_real_signed_callback_and_booking_with_combo_through_gateway(pg, catalog, monkeypatch, notification_transport):
    monkeypatch.setattr(settings, "NOTIFICATION_TRANSPORT", notification_transport)
    # Keep actual VNPay signature verification; only replace external locks/email delivery.
    monkeypatch.setattr("app.services.payment_service.redis_client.lock", lambda *a, **k: nullcontext())
    monkeypatch.setattr("app.services.payment_service.SeatLockManager.unlock_seat", lambda *a, **k: True)
    monkeypatch.setattr("app.services.payment_service.send_payment_success_email_task.delay", lambda **k: None)
    with proxied(pg, catalog["user"]) as client:
        created = client.post("/api/bookings", json={
            "userId": catalog["user"].id, "showtimeId": catalog["show"].id,
            "totalAmount": 185000, "paymentMethod": "VNPAY",
            "seats": [{"seat_id": catalog["seat"].id, "price": 1}],
            "foodItems": [{"food_item_id": 6, "quantity": 1}],
        })
        assert created.status_code == 201
        from app.models import Booking
        booking = pg.get(Booking, created.json()["bookingId"])
        attempt = PaymentRepository.create_attempt(pg, booking)
        params = provider_params(attempt)
        params["vnp_OrderInfo"] = "Vé phim + combo"
        signed = "&".join(f"{key}={quote_plus(str(value))}" for key, value in sorted(params.items()))
        params["vnp_SecureHash"] = hmac.new(settings.HASH_SECRET.encode(), signed.encode(), hashlib.sha512).hexdigest()
        callback = client.get("/api/payment/vnpay-ipn?" + urlencode(params))
        assert callback.status_code == 200 and callback.json()["RspCode"] == "00"
        detail = client.get(f"/api/bookings/{booking.id}").json()
        assert detail["bookingStatus"] == "CONFIRMED" and detail["totalAmount"] == 185000
        assert len(detail["foodItems"]) == 1
        if notification_transport == "events":
            from cinema_platform.events import OutboxRecord
            from notification_service.delivery import EmailData
            from sqlalchemy import select
            event = pg.execute(select(OutboxRecord).where(
                OutboxRecord.aggregate_id == f"booking:{booking.id}",
                OutboxRecord.destination == "notification",
            )).scalar_one()
            payload = EmailData.model_validate(event.payload["data"])
            assert payload.booking_detail.foodItems[0].quantity == 1
