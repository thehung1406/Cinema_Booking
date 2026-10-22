"""Executable UC01–UC07 HTTP tests, isolated from production DB and Redis.

SQLite covers transactions/contracts here. PostgreSQL row-lock concurrency is tested
separately when TEST_POSTGRES_URL points to an isolated migrated database.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlmodel import select

from test_ai_features import db  # isolated SQL fixture, JSONB compiler and test settings
from app.core.database import get_session
from app.models import (Booking, BookingDetail, CinemaRoom, Film, FilmFormat, Genre,
    KnowledgeChunk, KnowledgeDocument, Payment, Permission, Review, ReviewSentiment,
    Role, RolePermission, Seat, SeatStatus, SeatType, Showtime, Ticket, User)
from app.router.admin import router
from app.router.access_control import router as access_router
from app.services import rag_service
from app.services.auth_service import AuthService
from app.utils.dependencies import get_current_user, get_optional_current_user
from app.utils.security import create_access_token


@pytest.fixture
def setup(db):
    db.add_all([Role(id=3, code="ADMIN", name="Quản trị viên"), Role(id=4, code="MANAGER", name="Quản lý")])
    db.flush()
    codes = ["films.manage", "rooms.manage", "showtimes.manage", "seat_types.manage",
        "users.manage", "roles.manage", "knowledge.manage", "reports.view"]
    for code in codes:
        p = Permission(code=code, name=code)
        db.add(p); db.flush()
        db.add(RolePermission(role_id=3, permission_id=p.id))
        if code in codes[:4]:
            db.add(RolePermission(role_id=4, permission_id=p.id))
    db.add_all([User(id=4, username="admin", email="admin@example.com", password="unused", role_id=3),
        User(id=5, username="manager", email="manager@example.com", password="unused", role_id=4),
        Genre(id=1, name="Hành động"), FilmFormat(film_id=1, format_id=1),
        Seat(id=1, room_id=1, seat_type_id=1, seat_name="A1")])
    film = db.get(Film, 1)
    film.duration_minutes = 120
    film.release_date, film.end_date = date.today()-timedelta(days=1), date.today()+timedelta(days=90)
    db.commit()
    return db


@pytest.fixture
def client(setup):
    app = FastAPI()
    app.include_router(router); app.include_router(access_router)
    app.dependency_overrides[get_session] = lambda: setup
    app.dependency_overrides[get_current_user] = lambda: setup.get(User, 4)
    with TestClient(app) as client:
        client.app_under_test = app
        yield client


def film_body(**changes):
    return {"title": "Phim mới", "duration_minutes": 120, "release_date": date.today().isoformat(),
        "end_date": (date.today()+timedelta(days=30)).isoformat(), "genre_ids": [1], "format_ids": [1], **changes}


def show_body(**changes):
    return {"film_id": 1, "room_id": 1, "format_id": 1,
        "show_date": (date.today()+timedelta(days=1)).isoformat(), "start_time": "16:00", "end_time": "18:00", **changes}


def test_permissions_are_enforced_on_every_management_resource(client, setup):
    app = client.app_under_test
    for user_id in (1, 5):
        app.dependency_overrides[get_current_user] = lambda: setup.get(User, user_id)
        for path in ("employees", "documents", "reports?start_date=2026-01-01&end_date=2026-01-02"):
            assert client.get(f"/admin/{path}").status_code == 403
        assert client.get("/access-control/roles").status_code == 403
        assert client.put("/access-control/users/1/role", json={"role_id": 3}).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: setup.get(User, 5)
    assert set(client.get("/admin/session").json()["permissions"]) == set([
        "films.manage", "rooms.manage", "showtimes.manage", "seat_types.manage"])
    assert client.post("/admin/films", json=film_body()).status_code == 201
    app.dependency_overrides[get_current_user] = lambda: setup.get(User, 1)
    for path in ("session", "catalog", "films", "rooms", "showtimes", "prices", "rooms/1/seats"):
        assert client.get(f"/admin/{path}").status_code == 403
    assert client.post("/admin/rooms/1/seats", json={"seat_type_id": 1, "seat_name": "A2"}).status_code == 403


def test_film_links_crud_search_and_transactional_validation(client, setup):
    response = client.post("/admin/films", json=film_body())
    assert response.status_code == 201, response.text
    film_id = response.json()["id"]
    assert response.json()["genre_ids"] == [1] and response.json()["format_ids"] == [1]
    assert setup.get(FilmFormat, (film_id, 1))
    assert client.get("/admin/films", params={"q": "Phim mới"}).json()["total"] == 1
    assert client.get("/admin/films", params={"q": "%"}).json()["total"] == 0
    assert client.post("/admin/films", json=film_body(genre_ids=[999])).status_code == 400
    assert client.put(f"/admin/films/{film_id}", json=film_body(title="Tên đã sửa")).status_code == 200
    assert client.delete(f"/admin/films/{film_id}").status_code == 200
    assert client.delete("/admin/films/1").status_code == 409  # existing schedule
    assert client.post("/admin/films", json=film_body(end_date="2000-01-01")).status_code == 422
    assert client.put("/admin/films/1", json=film_body(duration_minutes=200)).status_code == 409


def test_rooms_seats_capacity_duplicates_and_room_ownership(client, setup):
    created = client.post("/admin/rooms", json={"theater_id": 1, "name": "Phòng mới", "capacity": 1})
    assert created.status_code == 201
    room_id = created.json()["id"]
    price = client.post("/admin/prices", json={"room_id": room_id, "name": "Thường", "base_price": 0})
    assert price.status_code == 201  # SD04 permits non-negative prices
    price_id = price.json()["id"]
    assert client.post(f"/admin/rooms/{room_id}/seats", json={"seat_type_id": 1, "seat_name": "A1"}).status_code == 400
    seat = client.post(f"/admin/rooms/{room_id}/seats", json={"seat_type_id": price_id, "seat_name": "a1"})
    assert seat.status_code == 201 and seat.json()["seat_name"] == "A1"
    seat_id = seat.json()["id"]
    assert client.post(f"/admin/rooms/{room_id}/seats", json={"seat_type_id": price_id, "seat_name": "A2"}).status_code == 409
    assert client.post("/admin/rooms/1/seats", json={"seat_type_id": 1, "seat_name": "A1"}).status_code == 409
    assert client.put(f"/admin/rooms/{room_id}/seats/{seat_id}", json={"seat_type_id": price_id, "seat_name": "B1"}).status_code == 200
    assert client.delete(f"/admin/prices/{price_id}").status_code == 409
    assert client.delete(f"/admin/rooms/{room_id}/seats/{seat_id}").status_code == 200
    assert client.delete(f"/admin/prices/{price_id}").status_code == 200
    assert client.delete(f"/admin/rooms/{room_id}").status_code == 200
    assert client.get(f"/admin/rooms/{room_id}/seats").status_code == 404
    assert client.delete("/admin/rooms/1").status_code == 409


def test_room_maintenance_checks_upcoming_schedules_without_rewriting_history(client, setup):
    body = {"theater_id": 1, "name": "Phòng 1", "capacity": 10, "status": "MAINTENANCE"}
    assert client.put("/admin/rooms/1", json=body).status_code == 409
    show = setup.get(Showtime, 1)
    show.show_date = date.today()-timedelta(days=1)
    setup.commit()
    assert client.put("/admin/rooms/1", json=body).status_code == 200
    assert client.post("/admin/showtimes", json=show_body()).status_code == 409


def test_showtime_duration_formats_conflicts_and_crud(client, setup):
    created = client.post("/admin/showtimes", json=show_body())
    assert created.status_code == 201, created.text
    show_id = created.json()["id"]
    assert client.post("/admin/showtimes", json=show_body(start_time="17:00", end_time="19:00")).status_code == 409
    assert client.post("/admin/showtimes", json=show_body(start_time="18:00", end_time="20:00")).status_code == 201  # adjacent slots
    assert client.post("/admin/showtimes", json=show_body(start_time="12:00", end_time="13:00")).status_code == 400
    assert client.post("/admin/showtimes", json=show_body(format_id=999)).status_code == 400
    assert client.post("/admin/showtimes", json=show_body(start_time="23:00", end_time="01:00")).status_code == 422
    assert client.post("/admin/showtimes", json=show_body(show_date="2000-01-01")).status_code == 400
    assert client.put(f"/admin/showtimes/{show_id}", json=show_body(start_time="12:00", end_time="14:00")).status_code == 200
    assert client.get("/admin/showtimes?show_date=invalid").status_code == 422
    assert client.delete(f"/admin/showtimes/{show_id}").status_code == 200


def add_booking(db):
    b = Booking(user_id=1, showtime_id=1, total_amount=Decimal("75000"),
        payment_status="PAID", booking_status="CONFIRMED")
    db.add(b); db.flush()
    detail = BookingDetail(booking_id=b.id, seat_id=1, price=Decimal("75000"))
    db.add(detail); db.flush()
    db.add_all([Ticket(booking_detail_id=detail.id, ticket_code=f"ticket-{b.id}"),
        Payment(booking_id=b.id, provider="VNPAY", payment_method="Online", amount=b.total_amount,
            merchant_ref=f"ref-{b.id}", status="PAID"),
        Payment(booking_id=b.id, provider="VNPAY", payment_method="Online", amount=b.total_amount,
            merchant_ref=f"retry-{b.id}", status="FAILED"),
        SeatStatus(showtime_id=1, seat_id=1, status="BOOKED")])
    db.commit()
    return b, detail


def test_booked_records_are_protected_and_prices_are_snapshots(client, setup):
    booking, detail = add_booking(setup)
    response = client.put("/admin/prices/1", json={"room_id": 1, "name": "Standard", "base_price": "99000"})
    assert response.status_code == 200
    setup.refresh(detail); setup.refresh(booking)
    assert detail.price == Decimal("75000") and booking.total_amount == Decimal("75000")
    assert client.put("/admin/showtimes/1", json=show_body()).status_code == 409
    assert client.delete("/admin/showtimes/1").status_code == 409
    assert client.put("/admin/rooms/1/seats/1", json={"seat_name": "B1", "seat_type_id": 1}).status_code == 409
    assert client.delete("/admin/rooms/1/seats/1").status_code == 409


def document_body(**changes):
    return {"source_id": "policy", "title": "Hướng dẫn đặt vé", "version": "1.0", "source_url": "/about",
        "effective_at": "2020-01-01T00:00:00Z", "content": "Đặt vé trực tuyến bằng cách chọn phim và giữ ghế.", **changes}


def approval(doc, **changes):
    stamp = doc["updated_at"]
    if not stamp.endswith("Z") and "+" not in stamp:
        stamp += "Z"
    return {"version": doc["version"], "expected_updated_at": stamp, **changes}


def test_knowledge_review_version_checks_and_retrieval(client, setup):
    created = client.post("/admin/documents", json=document_body())
    assert created.status_code == 200, created.text
    doc = created.json()
    assert doc["approved"] is False
    assert not rag_service.retrieve(setup, "đặt vé trực tuyến")
    view = client.get(f"/admin/documents/{doc['id']}").json()
    assert view["chunks"] and "embedding" not in view["chunks"][0]
    assert client.put(f"/admin/documents/{doc['id']}/approval", json=approval(doc, version="stale")).status_code == 409
    assert client.put(f"/admin/documents/{doc['id']}/approval", json=approval(doc)).status_code == 200
    assert rag_service.retrieve(setup, "đặt vé trực tuyến")
    assert client.post("/admin/documents", json=document_body(version="2.0")).status_code == 409
    latest = client.get(f"/admin/documents/{doc['id']}").json()
    update = client.post("/admin/documents", json=document_body(version="2.0", expected_updated_at=approval(latest)["expected_updated_at"], content="Hướng dẫn giữ ghế mới."))
    assert update.status_code == 200 and update.json()["approved"] is False
    assert not rag_service.retrieve(setup, "đặt vé trực tuyến")
    assert client.put(f"/admin/documents/{doc['id']}/approval", json=approval(latest)).status_code == 409
    assert client.delete(f"/admin/documents/{doc['id']}").status_code == 200
    assert not setup.exec(select(KnowledgeChunk)).all()
    assert client.post("/admin/documents", json=document_body(source_url="javascript:alert(1)")).status_code == 422
    assert client.post("/admin/documents", json=document_body(approved=True)).status_code == 422


def test_future_and_unprocessed_documents_do_not_become_retrievable(client, setup):
    doc = client.post("/admin/documents", json=document_body(effective_at="2099-01-01T00:00:00Z")).json()
    assert client.put(f"/admin/documents/{doc['id']}/approval", json=approval(doc)).status_code == 200
    assert not rag_service.retrieve(setup, "đặt vé trực tuyến")
    chunk = setup.exec(select(KnowledgeChunk)).first()
    chunk.embedding_version = "old-version"; setup.commit()
    doc = client.get(f"/admin/documents/{doc['id']}").json()
    assert client.put(f"/admin/documents/{doc['id']}/approval", json=approval(doc)).status_code == 409


def test_failed_document_processing_rolls_back_document_and_chunks(client, setup, monkeypatch):
    doc = client.post("/admin/documents", json=document_body()).json()
    client.put(f"/admin/documents/{doc['id']}/approval", json=approval(doc))
    current = client.get(f"/admin/documents/{doc['id']}").json()

    def processing_error(_):
        raise RuntimeError("test processing failure")

    monkeypatch.setattr(rag_service, "embed", processing_error)
    with pytest.raises(RuntimeError, match="test processing failure"):
        client.post("/admin/documents", json=document_body(version="2.0", content="Nội dung mới",
            expected_updated_at=approval(current)["expected_updated_at"]))
    setup.expire_all()
    unchanged = client.get(f"/admin/documents/{doc['id']}").json()
    assert unchanged["version"] == "1.0" and unchanged["approved"] is True
    assert unchanged["chunks"] == current["chunks"]


def test_employee_management_safe_responses_role_assignment_and_locking(client, setup, monkeypatch):
    created = client.post("/admin/employees", json={"username": "new.staff", "password": "test-password-123", "email": "staff-new@example.com", "full_name": "Nhân viên mới", "role_id": 2})
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]
    assert "password" not in created.json()
    assert "password" not in client.get("/admin/employees").json()["items"][0]
    assert client.put(f"/admin/employees/{user_id}", json={"full_name": "Tên mới", "email": "staff-new@example.com", "phone": "0900000000"}).status_code == 200
    assert client.put(f"/access-control/users/{user_id}/role", json={"role_id": 4}).status_code == 200
    assert setup.get(User, user_id).role_id == 4
    assert client.put("/access-control/users/4/role", json={"role_id": 1}).status_code == 409
    assert client.put("/access-control/roles/3/permissions", json={"permission_ids": []}).status_code == 409
    assert client.put(f"/admin/employees/{user_id}/status", json={"is_active": False}).status_code == 200
    assert client.put("/admin/employees/4/status", json={"is_active": False}).status_code == 409
    monkeypatch.setattr("app.utils.dependencies.redis_client.get", lambda key: None)
    token = create_access_token({"sub": str(user_id)})
    with pytest.raises(HTTPException) as locked:
        get_current_user(token=token, session=setup)
    assert locked.value.status_code == 403
    assert get_optional_current_user(token=token, session=setup) is None
    with pytest.raises(HTTPException):
        AuthService.login(setup, "new.staff", "test-password-123")
    assert client.put(f"/admin/employees/{user_id}/status", json={"is_active": True}).status_code == 200
    assert get_current_user(token=token, session=setup).id == user_id


def test_report_paid_bookings_are_not_multiplied_and_sentiments_are_current(client, setup):
    booking, _ = add_booking(setup)
    now = datetime.now(timezone.utc)
    reviews = [Review(user_id=i, film_id=1, content="Nội dung đánh giá", moderation_status="approved", content_version=2, updated_at=now) for i in (1, 2, 3)]
    setup.add_all(reviews); setup.flush()
    setup.add_all([ReviewSentiment(review_id=reviews[0].id, content_version=2, status="succeeded", label="positive"),
        ReviewSentiment(review_id=reviews[1].id, content_version=1, status="succeeded", label="negative"),
        ReviewSentiment(review_id=reviews[2].id, content_version=2, status="pending")])
    setup.commit()
    params = {"start_date": (date.today()-timedelta(days=1)).isoformat(), "end_date": (date.today()+timedelta(days=2)).isoformat()}
    response = client.get("/admin/reports", params=params)
    assert response.status_code == 200, response.text
    report = response.json()
    assert Decimal(str(report["revenue"])) == 75000 and report["booking_count"] == 1
    assert report["ticket_count"] == 1 and report["occupancy"] == 100
    assert report["sentiments"] == {"positive": 1, "neutral": 0, "negative": 0, "total": 3, "pending": 2, "coverage": 33.33}
    assert report["by_film"][0]["tickets"] == 1
    empty = client.get("/admin/reports", params={**params, "film_id": 999}).json()
    assert Decimal(str(empty["revenue"])) == 0 and empty["occupancy"] == 0 and not empty["by_film"]
    invalid = client.get("/admin/reports", params={"start_date": "2026-10-20", "end_date": "2026-10-01"})
    assert invalid.status_code == 422
    # A provider success alone is insufficient when the order has not been confirmed.
    booking.booking_status = "PENDING"; setup.commit()
    assert client.get("/admin/reports", params=params).json()["booking_count"] == 0
