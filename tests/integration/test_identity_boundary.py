import sys
from pathlib import Path
from uuid import uuid4
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend/tests"))
sys.path.insert(0, str(ROOT / "services/identity-service/tests"))
sys.path.insert(0, str(ROOT / "services/ai-service/tests"))
sys.path.insert(0, str(ROOT / "services/review-service/tests"))
from test_normalized_schema import pg, catalog, provider, provider_params
from identity_support import identity_store, identity_settings, identity_client, register, login, bearer
from ai_support import ai_store, ai_settings, FakeCache
from review_support import review_store, review_settings
from app.core.config import settings
from app.core.database import get_session
from app.models import User, SeatStatus, Booking
from app.models.migration_ownership import DomainOwnership
from app.services import identity_remote
from app.utils.dependencies import get_current_user, require_permission
from app.utils.identity_ownership import require_legacy_identity_owner
from app.worker.ai_ownership import set_owner
from app.repositories.booking_repo import BookingRepository
from app.repositories.payment_repo import PaymentRepository
from app.services.payment_service import PaymentService


def test_db_fence_blocks_raw_legacy_writers_even_after_env_reset(pg, catalog, monkeypatch):
    monkeypatch.setattr(settings, "IDENTITY_STORAGE_OWNER", "monolith")
    set_owner(pg, "maintenance", "Identity test freeze", domain="identity")
    pg.flush()
    with pytest.raises(HTTPException) as blocked:
        require_legacy_identity_owner(pg)
    assert blocked.value.status_code == 503
    with pytest.raises(DBAPIError, match="Identity legacy writer"):
        with pg.begin_nested():
            pg.execute(text("UPDATE users SET is_active=false WHERE id=:id"), {"id": catalog["user"].id})
    set_owner(pg, "service", "Identity copied and verified", domain="identity")
    pg.flush()
    with pytest.raises(HTTPException) as blocked:
        require_legacy_identity_owner(pg)
    assert blocked.value.status_code == 410
    with pytest.raises(ValueError):
        set_owner(pg, "monolith", "Unsafe rollback", domain="identity")


def test_new_identity_user_holds_books_confirms_reviews_and_chats_without_legacy_user(
        pg, catalog, provider, identity_client, identity_store, identity_settings,
        ai_store, ai_settings, review_store, review_settings, monkeypatch):
    from main import app
    from app.router.internal_review_read import authors, Authors
    from ai_service.main import create_app as ai_app
    from review_service.main import create_app as review_app
    with identity_store.begin() as conn:
        conn.execute(text("SELECT setval(pg_get_serial_sequence('users','id'),1000000000,true)"))
    user = register(identity_client)
    pair = login(identity_client)
    set_owner(pg, "maintenance", "Test freeze", domain="identity")
    set_owner(pg, "service", "Test copy verified", domain="identity")
    pg.flush()
    monkeypatch.setattr(settings, "IDENTITY_STORAGE_OWNER", "service")
    monkeypatch.setattr(settings, "NOTIFICATION_TRANSPORT", "events")
    def call(path, body):
        response = identity_client.post(path, headers={"X-Service-Key": identity_settings.service_key}, json=body)
        if response.status_code != 200:
            raise HTTPException(response.status_code, "Identity rejected request")
        return response.json()
    monkeypatch.setattr(identity_remote, "call", call)
    principal = get_current_user(token=pair["access_token"], session=pg)
    assert principal.id == user["id"] and pg.get(User, principal.id) is None
    with pytest.raises(HTTPException):
        require_permission("tickets.check_in")(user=principal, session=pg)
    # Actual hold + booking services accept an external ID with no source account.
    from app.services.seat_service import SeatService
    from app.services.booking_service import BookingService
    from app.schemas.booking import BookingCreateRequest
    hold = pg.exec(select(SeatStatus).where(SeatStatus.seat_id == catalog["seat"].id)).scalar_one()
    hold.status, hold.hold_by_user_id, hold.hold_expired_at = "AVAILABLE", None, None
    pg.add(hold)
    pg.flush()
    monkeypatch.setattr("app.services.seat_service.SeatLockManager.lock_seat", lambda **kw: True)
    assert SeatService.hold_seats(pg, catalog["show"].id, [catalog["seat"].id], principal.id)[0]["status"] == "HOLD"
    created = BookingService.create_booking(pg, BookingCreateRequest(userId=principal.id,
        showtimeId=catalog["show"].id, totalAmount=75000, paymentMethod="VNPAY",
        seats=[{"seat_id": catalog["seat"].id, "price": 75000}]), principal.id)
    booking = pg.get(Booking, created.bookingId)
    assert booking.customer_email == user["email"]
    attempt = PaymentRepository.create_attempt(pg, booking)
    # Provider confirmation and histories remain independent of Identity availability.
    monkeypatch.setattr(identity_remote, "call", lambda *a: pytest.fail("Confirmation must use booking snapshot"))
    assert PaymentService.process_vnpay_ipn(pg, provider_params(attempt))["RspCode"] == "00"
    assert BookingRepository.get_booking_with_details(pg, booking.id)["email"] == user["email"]
    assert len(BookingRepository.get_user_bookings_with_details(pg, principal.id)) == 1
    monkeypatch.setattr(identity_remote, "call", call)
    facts = authors(Authors(items=[{"user_id": principal.id, "film_id": catalog["film"].id}]), db=pg)
    assert facts[0]["author"] == "customer" and facts[0]["verified_purchase"]
    def auth(request):
        import json
        response = identity_client.post("/internal/v1/auth/introspect", headers={"X-Service-Key": identity_settings.service_key}, json=json.loads(request.content))
        return httpx.Response(response.status_code, json=response.json())
    def reads(request):
        if request.url.path.endswith("/matches"):
            return httpx.Response(200, json={"film_id": [], "theater_id": []})
        if request.url.path.endswith("/context"):
            return httpx.Response(200, json={"film_name": None, "theater_name": None})
        if "/films/" in request.url.path:
            return httpx.Response(200, json={"id": catalog["film"].id, "title": "Test", "image": None})
        if request.url.path.endswith("/authors"):
            return httpx.Response(200, json=facts)
        return httpx.Response(200, json=[])
    with TestClient(ai_app(ai_settings, engine=ai_store, cache=FakeCache(), auth_transport=httpx.MockTransport(auth),
                          read_transport=httpx.MockTransport(reads))) as ai:
        chat = ai.post("/ai/chat", headers=bearer(pair), json={"message": "Xin chào"})
        assert chat.status_code == 200, chat.text
        cid = chat.json()["conversation_id"]
        assert ai.get(f"/ai/conversations/{cid}", headers=bearer(pair)).status_code == 200
        other = register(identity_client, "other")
        other_pair = login(identity_client, "other")
        assert ai.get(f"/ai/conversations/{cid}", headers=bearer(other_pair)).status_code == 404
    with TestClient(review_app(review_settings, engine=review_store, auth_transport=httpx.MockTransport(auth),
                              read_transport=httpx.MockTransport(reads))) as reviews:
        response = reviews.post(f'/films/{catalog["film"].id}/reviews', headers=bearer(pair), json={"content": "Phim hay"})
        assert response.status_code in {200, 201}, response.text
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = lambda: pg
    try:
        with TestClient(app) as backend:
            assert backend.get(f"/bookings/{booking.id}", headers=bearer(other_pair)).status_code == 403
            assert backend.get(f"/bookings/{booking.id}", headers=bearer(pair)).status_code == 200
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)
    assert pg.get(User, user["id"]) is None


def test_identity_outage_fails_closed_without_archive_fallback(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_KEY", "isolated-service-key-at-least-32-characters")
    class Offline(httpx.Client):
        def post(self, *args, **kwargs):
            raise httpx.ConnectError("offline")
    monkeypatch.setattr(identity_remote.httpx, "Client", Offline)
    with pytest.raises(HTTPException) as error:
        identity_remote.context("token")
    assert error.value.status_code == 503
