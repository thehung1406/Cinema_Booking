"""PostgreSQL integration tests. Point TEST_POSTGRES_URL at a migrated test DB.

Each test runs inside a rolled-back outer transaction, including API commits.
"""
import os
from contextlib import nullcontext
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, Session, create_engine, select
from app.models import (User, Role, Permission, RolePermission, Film, Genre, Format,
    FilmFormat, Theater, CinemaRoom, SeatType, Seat, Showtime, SeatStatus, Booking,
    BookingDetail, Payment, Ticket)
from app.schemas.film import FilmDetailRead
from app.schemas.auth import UserRead
from app.repositories.payment_repo import PaymentRepository
from app.services.payment_service import PaymentService
from app.services.ticket_service import TicketService
from app.core.config import settings
from app.core.database import get_session
from app.utils.dependencies import get_current_user, require_permission


@pytest.fixture
def pg():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL is required for actual PostgreSQL constraints")
    engine = create_engine(url)
    if "test" not in engine.url.database.lower():
        pytest.fail("Use an isolated database with 'test' in its name")
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
    engine.dispose()


@pytest.fixture
def catalog(pg):
    suffix = uuid4().hex[:10]
    role = pg.exec(select(Role).where(Role.code == "USER")).one()
    user = User(username=suffix, email=f"{suffix}@example.com", password="unused", role_id=role.id)
    film = Film(title=f"Test {suffix}", duration_minutes=120,
                genre_items=[Genre(name=f"Genre {suffix}")])
    format = Format(code=suffix.upper(), name=f"Format {suffix}")
    theater = Theater(name="Test theater", city="Test", address="Test")
    pg.add_all([user, film, format, theater])
    pg.flush()
    film.format_items.append(format)
    room = CinemaRoom(theater_id=theater.id, name="Room", capacity=10)
    pg.add(room)
    pg.flush()
    seat_type = SeatType(room_id=room.id, name="Standard", base_price=Decimal("75000"))
    pg.add(seat_type)
    pg.flush()
    seat = Seat(room_id=room.id, seat_type_id=seat_type.id, seat_name="A1")
    show = Showtime(film_id=film.id, room_id=room.id, format_id=format.id,
                    show_date=date.today()+timedelta(days=5), start_time=time(18), end_time=time(20))
    pg.add_all([seat, show])
    pg.flush()
    booking = Booking(user_id=user.id, showtime_id=show.id, total_amount=Decimal("75000"),
                      payment_method="VNPAY", expires_at=datetime.now(timezone.utc)+timedelta(minutes=10))
    pg.add(booking)
    pg.flush()
    detail = BookingDetail(booking_id=booking.id, seat_id=seat.id, price=Decimal("75000"))
    hold = SeatStatus(seat_id=seat.id, showtime_id=show.id, status="HOLD", hold_by_user_id=user.id,
                      hold_expired_at=booking.expires_at)
    pg.add_all([detail, hold])
    pg.flush()
    return dict(user=user, film=film, format=format, theater=theater, room=room,
                seat_type=seat_type, seat=seat, show=show, booking=booking, detail=detail)


def provider_params(payment, response="00"):
    return {"vnp_TxnRef": payment.merchant_ref, "vnp_TmnCode": settings.TMN_CODE,
            "vnp_Amount": str(int(payment.amount * 100)), "vnp_ResponseCode": response,
            "vnp_TransactionStatus": response, "vnp_TransactionNo": uuid4().hex}


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr("app.services.payment_service.redis_client.lock", lambda *a, **k: nullcontext())
    monkeypatch.setattr("app.services.payment_service.SeatLockManager.unlock_seat", lambda *a, **k: True)
    monkeypatch.setattr("app.services.payment_service.send_payment_success_email_task.delay", lambda **k: None)
    monkeypatch.setattr("app.router.payment.verify_vnpay_signature", lambda params: True)


def test_all_23_tables_and_api_compatibility(pg, catalog):
    assert len(SQLModel.metadata.tables) == 23
    assert set(SQLModel.metadata.tables) <= set(inspect(pg.bind).get_table_names())
    film = FilmDetailRead.model_validate(catalog["film"])
    assert film.duration == "120 phút" and film.genre.startswith("Genre ")
    assert film.formats == [catalog["format"].name]
    assert "genre" not in Film.__table__.columns and "formats" not in Film.__table__.columns
    assert UserRead.model_validate(catalog["user"], from_attributes=True).role == "USER"


def test_format_must_be_supported_by_film(pg, catalog):
    unsupported = Format(code=uuid4().hex[:10], name="Unsupported")
    pg.add(unsupported)
    pg.flush()
    with pytest.raises(IntegrityError):
        with pg.begin_nested():
            pg.add(Showtime(film_id=catalog["film"].id, room_id=catalog["room"].id,
                format_id=unsupported.id, show_date=date.today()+timedelta(days=6),
                start_time=time(18), end_time=time(20)))
            pg.flush()


def test_availability_and_hold_respect_inactive_seats(pg, catalog, monkeypatch):
    from app.services.seat_service import SeatService
    monkeypatch.setattr("app.services.seat_service.SeatLockManager.get_all_locks_for_showtime",
                        lambda showtime_id: [])
    show_id, seat = catalog["show"].id, catalog["seat"]
    assert SeatService.get_available_seats_count(pg, show_id) == 0  # DB hold, Redis empty
    hold = pg.exec(select(SeatStatus).where(SeatStatus.seat_id == seat.id,
                                          SeatStatus.showtime_id == show_id)).one()
    hold.hold_expired_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    pg.add(hold)
    pg.flush()
    assert SeatService.get_available_seats_count(pg, show_id) == 1
    seat.status = "INACTIVE"
    pg.add(seat)
    pg.flush()
    assert SeatService.get_available_seats_count(pg, show_id) == 0
    assert SeatService.get_seats_by_showtime(pg, show_id)[0]["status"] == "UNAVAILABLE"
    with pytest.raises(HTTPException) as error:
        SeatService.hold_seats(pg, show_id, [seat.id], catalog["user"].id)
    assert error.value.status_code == 409


@pytest.mark.parametrize("table", ["detail", "status", "seat"])
def test_cross_room_seats_rejected(pg, catalog, table):
    room = CinemaRoom(theater_id=catalog["theater"].id, name="Other", capacity=10)
    pg.add(room)
    pg.flush()
    seat_type = SeatType(room_id=room.id, name="Other", base_price=Decimal("75000"))
    pg.add(seat_type)
    pg.flush()
    seat = Seat(room_id=room.id, seat_type_id=seat_type.id, seat_name="B1")
    pg.add(seat)
    pg.flush()
    with pytest.raises(IntegrityError):
        with pg.begin_nested():
            if table == "detail":
                pg.add(BookingDetail(booking_id=catalog["booking"].id, seat_id=seat.id, price=75000))
            elif table == "status":
                pg.add(SeatStatus(showtime_id=catalog["show"].id, seat_id=seat.id))
            else:
                pg.add(Seat(room_id=room.id, seat_type_id=catalog["seat_type"].id, seat_name="B2"))
            pg.flush()


@pytest.mark.parametrize("start,end", [(time(19), time(21)), (time(17), time(19))])
def test_overlapping_showtimes_rejected(pg, catalog, start, end):
    with pytest.raises(IntegrityError):
        with pg.begin_nested():
            pg.add(Showtime(film_id=catalog["film"].id, room_id=catalog["room"].id,
                format_id=catalog["format"].id, show_date=catalog["show"].show_date,
                start_time=start, end_time=end))
            pg.flush()


def test_adjacent_showtimes_allowed(pg, catalog):
    pg.add(Showtime(film_id=catalog["film"].id, room_id=catalog["room"].id,
        format_id=catalog["format"].id, show_date=catalog["show"].show_date,
        start_time=time(20), end_time=time(22)))
    pg.flush()


def test_overnight_overlap_rejected(pg, catalog):
    day = catalog["show"].show_date + timedelta(days=2)
    pg.add(Showtime(film_id=catalog["film"].id, room_id=catalog["room"].id,
        format_id=catalog["format"].id, show_date=day, start_time=time(23), end_time=time(1)))
    pg.flush()
    with pytest.raises(IntegrityError):
        with pg.begin_nested():
            pg.add(Showtime(film_id=catalog["film"].id, room_id=catalog["room"].id,
                format_id=catalog["format"].id, show_date=day+timedelta(days=1),
                start_time=time(0, 30), end_time=time(2)))
            pg.flush()


def test_ticket_not_issued_for_pending_booking(pg, catalog):
    with pytest.raises(HTTPException):
        TicketService.issue_for_booking(pg, catalog["booking"])
    with pytest.raises(IntegrityError):
        with pg.begin_nested():
            pg.add(Ticket(booking_detail_id=catalog["detail"].id, ticket_code=uuid4().hex))
            pg.flush()


def test_payment_callback_idempotency_and_checkin(pg, catalog, provider):
    booking = catalog["booking"]
    attempt = PaymentRepository.create_attempt(pg, booking)
    params = provider_params(attempt)
    assert PaymentService.resolve_booking_id(pg, params["vnp_TxnRef"]) == booking.id
    for _ in range(2):
        result = PaymentService.confirm_vnpay_payment(pg, booking.id, "00", params)
        assert result["status"] == "success"
    tickets = pg.exec(select(Ticket).where(Ticket.booking_detail_id == catalog["detail"].id)).all()
    assert len(tickets) == 1 and pg.get(Payment, attempt.id).status == "PAID"
    assert pg.get(Booking, booking.id).payment_status == "PAID"
    assert TicketService.check_in(pg, tickets[0].ticket_code).status == "USED"
    with pytest.raises(HTTPException) as duplicate:
        TicketService.check_in(pg, tickets[0].ticket_code)
    assert duplicate.value.status_code == 409


def test_ipn_duplicate_and_failed_callback_dont_undo_paid(pg, catalog, provider):
    attempt = PaymentRepository.create_attempt(pg, catalog["booking"])
    params = provider_params(attempt)
    assert PaymentService.process_vnpay_ipn(pg, params)["RspCode"] == "00"
    assert PaymentService.process_vnpay_ipn(pg, params)["RspCode"] == "02"
    failed = dict(params, vnp_ResponseCode="24", vnp_TransactionStatus="24")
    PaymentService.process_vnpay_ipn(pg, failed)
    assert pg.get(Payment, attempt.id).status == "PAID"
    assert pg.get(Booking, catalog["booking"].id).payment_status == "PAID"


def test_wrong_amount_cannot_issue_tickets(pg, catalog, provider):
    attempt = PaymentRepository.create_attempt(pg, catalog["booking"])
    params = dict(provider_params(attempt), vnp_Amount="100")
    assert PaymentService.process_vnpay_ipn(pg, params)["RspCode"] == "04"
    assert pg.exec(select(Ticket).where(Ticket.booking_detail_id == catalog["detail"].id)).first() is None
    assert attempt.status == "PENDING"


def test_expired_booking_records_provider_payment_without_issuing_ticket(pg, catalog, provider):
    booking = catalog["booking"]
    booking.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    pg.add(booking)
    pg.flush()
    attempt = PaymentRepository.create_attempt(pg, booking)
    result = PaymentService.confirm_vnpay_payment(pg, booking.id, "00", provider_params(attempt))
    assert result["status"] == "failed"
    assert pg.get(Payment, attempt.id).status == "PAID"
    assert pg.get(Booking, booking.id).booking_status == "EXPIRED"
    assert pg.exec(select(Ticket).where(Ticket.booking_detail_id == catalog["detail"].id)).first() is None


def test_unknown_reference_rejected(pg):
    with pytest.raises(HTTPException) as unknown:
        PaymentService.resolve_booking_id(pg, uuid4().hex)
    assert unknown.value.status_code == 404


def test_provider_result_survives_seat_confirmation_failure(pg, catalog, provider):
    hold = pg.exec(select(SeatStatus).where(SeatStatus.showtime_id == catalog["show"].id,
                                          SeatStatus.seat_id == catalog["seat"].id)).one()
    hold.status = "AVAILABLE"
    pg.add(hold)
    attempt = PaymentRepository.create_attempt(pg, catalog["booking"])
    pg.commit()
    with pytest.raises(HTTPException):
        PaymentService.confirm_vnpay_payment(pg, catalog["booking"].id, "00", provider_params(attempt))
    assert pg.get(Payment, attempt.id).status == "PAID"
    assert pg.get(Booking, catalog["booking"].id).payment_status == "PENDING"
    assert pg.exec(select(Ticket).where(Ticket.booking_detail_id == catalog["detail"].id)).first() is None


def test_registration_assigns_default_role_and_hashes_password(pg):
    from types import SimpleNamespace
    from app.services.auth_service import AuthService
    suffix = uuid4().hex[:10]
    data = SimpleNamespace(username=suffix, password="Strong-test-password", email=f"{suffix}@example.com",
                           full_name="Test user", phone=None)
    user = AuthService.register(pg, data)
    assert user.role == "USER" and user.password != data.password


def test_payment_attempt_history_and_provider_reference_unique(pg, catalog):
    first = PaymentRepository.create_attempt(pg, catalog["booking"])
    second = PaymentRepository.create_attempt(pg, catalog["booking"])
    assert first.merchant_ref != second.merchant_ref
    first.transaction_ref = "same-provider-id"
    pg.add(first)
    pg.flush()
    with pytest.raises(IntegrityError):
        with pg.begin_nested():
            second.transaction_ref = "same-provider-id"
            pg.add(second)
            pg.flush()


def test_catalog_deletion_preserves_booking_history(pg, catalog):
    with pytest.raises(IntegrityError):
        with pg.begin_nested():
            pg.exec(text("DELETE FROM films WHERE id=:id"), params={"id": catalog["film"].id})
            pg.flush()
    assert pg.get(Booking, catalog["booking"].id) is not None


def test_permission_is_checked_from_current_db(pg, catalog):
    check = require_permission("tickets.check_in")
    with pytest.raises(HTTPException) as forbidden:
        check(user=catalog["user"], session=pg)
    assert forbidden.value.status_code == 403
    permission = pg.exec(select(Permission).where(Permission.code == "tickets.check_in")).one()
    pg.add(RolePermission(role_id=catalog["user"].role_id, permission_id=permission.id))
    pg.flush()
    assert check(user=catalog["user"], session=pg).id == catalog["user"].id


def test_ticket_endpoint_enforces_ownership_and_checkin_permission(pg, catalog):
    from app.router.ticket import router
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = lambda: pg
    app.dependency_overrides[get_current_user] = lambda: catalog["user"]
    client = TestClient(app)
    assert client.get(f"/tickets/booking/{catalog['booking'].id}").status_code == 200
    assert client.post("/tickets/unknown/check-in").status_code == 403
    other = User(username=uuid4().hex[:10], email=f"{uuid4().hex}@example.test",
                 password="unused", role_id=catalog["user"].role_id)
    pg.add(other)
    pg.flush()
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.get(f"/tickets/booking/{catalog['booking'].id}").status_code == 403
