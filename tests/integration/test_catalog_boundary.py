from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import event, select, text
from sqlalchemy.exc import DBAPIError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend/tests"))
sys.path.insert(0, str(ROOT / "services/catalog-service/tests"))
from test_normalized_schema import pg, catalog, provider, provider_params
from catalog_support import catalog_store, catalog_settings, catalog_client, HEADERS, film_body
from app.models import Film, FoodItem, Format, Booking, Showtime
from app.core.config import settings
from app.services import catalog_remote, admin_service
from app.services.food_service import FoodService
from app.services.booking_service import BookingService
from app.services.seat_service import SeatService
from app.services.payment_service import PaymentService
from app.repositories.booking_repo import BookingRepository
from app.repositories.payment_repo import PaymentRepository
from app.schemas.admin import ShowtimeWrite
from app.schemas.booking import BookingCreateRequest
from app.schemas.food import FoodSelection
from app.worker.ai_ownership import set_owner
from app.utils.catalog_ownership import require_legacy_catalog_owner


def test_new_catalog_film_schedule_and_food_quote_work_without_mirrors_and_keep_history(
        pg, catalog, provider, catalog_client, catalog_store, catalog_settings, monkeypatch):
    from sqlalchemy.orm import Session as OwnerSession
    from catalog_service.models import Format as OwnerFormat
    from app.schemas.admin import ReportFilters
    from app.repositories.admin_repo import report
    from app.services.ai_tools import run_tool
    from app.schemas.ai import ToolCall, ToolContext
    from app.router.internal_review_read import film as review_film
    import re
    client = catalog_client
    new_format_id = 1000001
    with OwnerSession(catalog_store) as owner_db:
        owner_db.add(OwnerFormat(id=new_format_id, code="NEW", name="New format"))
        owner_db.commit()
    body = film_body(title="Independent Catalog film", format_ids=[new_format_id])
    created = client.post('/admin/films', headers=HEADERS, json=body)
    assert created.status_code == 201, created.text
    film_id = created.json()["id"]
    food = client.post('/admin/food-items', headers=HEADERS,
        json=dict(name="New popcorn", category="POPCORN", price="20000.00"))
    assert food.status_code == 201, food.text
    food_id = food.json()["id"]
    assert pg.get(Film, film_id) is None and pg.get(Format, new_format_id) is None and pg.get(FoodItem, food_id) is None
    def call(method, path, **kwargs):
        response = client.request(method, path, headers={"X-Service-Key": catalog_settings.service_key}, **kwargs)
        if response.status_code != 200:
            raise HTTPException(response.status_code, response.text)
        return response.json()
    monkeypatch.setattr(catalog_remote, "call", call)
    set_owner(pg, "maintenance", "Catalog test freeze", domain="catalog")
    set_owner(pg, "service", "Catalog copy verified", domain="catalog")
    pg.flush()
    monkeypatch.setattr(settings, "CATALOG_STORAGE_OWNER", "service")
    monkeypatch.setattr(settings, "NOTIFICATION_TRANSPORT", "events")
    queries = []
    def watch(conn, cursor, statement, *args): queries.append(statement.lower())
    event.listen(pg.bind, "before_cursor_execute", watch)
    try:
        show = admin_service.showtime_write(pg, ShowtimeWrite(film_id=film_id, format_id=new_format_id,
            room_id=catalog["room"].id, show_date=date.today()+timedelta(days=5), start_time=time(16), end_time=time(18)))
        assert show.catalog_binding_id and show.format == "New format"
        monkeypatch.setattr("app.services.seat_service.SeatLockManager.lock_seat", lambda **kw: True)
        SeatService.hold_seats(pg, show.id, [catalog["seat"].id], catalog["user"].id)
        request = BookingCreateRequest(userId=catalog["user"].id, showtimeId=show.id, totalAmount=1,
            paymentMethod="VNPAY", seats=[{"seat_id": catalog["seat"].id, "price": 0.01}],
            foodItems=[{"food_item_id": food_id, "quantity": 2}])
        with pytest.raises(HTTPException) as mismatch:
            BookingService.create_booking(pg, request, catalog["user"].id)
        assert mismatch.value.status_code == 400
        request.totalAmount = 115000
        created = BookingService.create_booking(pg, request, catalog["user"].id)
        booking = pg.get(Booking, created.bookingId)
        assert booking.food_quote_id and booking.food_quote_version == 1
        assert client.put(f'/admin/films/{film_id}', headers=HEADERS, json={**body,"title":"Renamed"}).status_code == 200
        assert client.put(f'/admin/food-items/{food_id}', headers=HEADERS,
            json=dict(name="Changed popcorn", category="POPCORN", price="50000.00")).status_code == 200
        attempt = PaymentRepository.create_attempt(pg, booking)
        monkeypatch.setattr(catalog_remote, "call", lambda *a, **k: pytest.fail("Provider confirmation/history must use snapshots"))
        # A Catalog freeze also leaves existing provider confirmations usable.
        with monkeypatch.context() as frozen:
            frozen.setattr(catalog_remote, "get_owner", lambda db=None: "maintenance")
            assert PaymentService.process_vnpay_ipn(pg, provider_params(attempt))["RspCode"] == "00"
            detail = BookingRepository.get_booking_with_details(pg, booking.id)
        assert detail["filmTitle"] == "Independent Catalog film"
        assert detail["foodItems"][0]["name"] == "New popcorn"
        assert detail["foodItems"][0]["unit_price"] == Decimal("20000.00")
        monkeypatch.setattr(catalog_remote, "call", call)
        stats = report(pg, ReportFilters(start_date=show.show_date, end_date=show.show_date, film_id=film_id))
        assert stats["revenue"] == Decimal("115000.00")
        assert stats["by_film"][0]["title"] == "Renamed"
        assert review_film(film_id, db=pg)["title"] == "Renamed"
        evidence = run_tool(pg, ToolCall(name="search_films", query="Renamed", context=ToolContext()))
        assert evidence[0]["id"] == f"film:{film_id}"
        assert not [q for q in queries if re.search(r'\b(from|join)\s+"?(films|genres|formats|film_formats|film_genres|food_items|combo_items)\b', q)]
    finally:
        event.remove(pg.bind, "before_cursor_execute", watch)
    assert pg.get(Film, film_id) is None and pg.get(FoodItem, food_id) is None


def test_db_fence_freezes_catalog_and_schedule_writers(pg, catalog, monkeypatch):
    monkeypatch.setattr(settings, "CATALOG_STORAGE_OWNER", "monolith")
    set_owner(pg, "maintenance", "Catalog test freeze", domain="catalog")
    pg.flush()
    with pytest.raises(HTTPException) as blocked:
        require_legacy_catalog_owner(pg)
    assert blocked.value.status_code == 503
    for sql, params in [
        ("UPDATE films SET title=title WHERE id=:id", {"id": catalog["film"].id}),
        ("UPDATE showtimes SET status=status WHERE id=:id", {"id": catalog["show"].id}),
    ]:
        with pytest.raises(DBAPIError):
            with pg.begin_nested(): pg.execute(text(sql), params)
    set_owner(pg, "service", "Catalog copy verified", domain="catalog")
    pg.flush()
    with pytest.raises(HTTPException) as blocked:
        require_legacy_catalog_owner(pg)
    assert blocked.value.status_code == 410
    with pytest.raises(DBAPIError):
        with pg.begin_nested():
            pg.execute(text("UPDATE showtimes SET start_time='17:00' WHERE id=:id"), {"id": catalog["show"].id})


def test_expired_quote_is_rejected_at_booking_snapshot_save(pg, catalog):
    quote = catalog_remote.Quote(id="11111111-1111-1111-1111-111111111111", version=1, lines=[], total="0", currency="VND", expires_at=datetime.now(timezone.utc)-timedelta(seconds=1))
    with pytest.raises(HTTPException) as error:
        FoodService.save(pg, catalog["booking"].id, catalog_remote.QuotedLines(quote))
    assert error.value.status_code == 409


def test_catalog_outage_never_falls_back_to_archive(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_KEY", "isolated-test-key-at-least-32-characters")
    class Offline(httpx.Client):
        def request(self, *args, **kwargs): raise httpx.ConnectError("offline")
    monkeypatch.setattr(catalog_remote.httpx, "Client", Offline)
    with pytest.raises(HTTPException) as error:
        catalog_remote.film_batch([1])
    assert error.value.status_code == 503
