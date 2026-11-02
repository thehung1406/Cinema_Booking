"""Booking consumes complete immutable Cinema versions without physical mirrors."""
from datetime import date,datetime,time,timedelta,timezone
from uuid import uuid4
from decimal import Decimal
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event,text
from sqlalchemy.exc import DBAPIError
from sqlmodel import select
from test_normalized_schema import pg,catalog,provider,provider_params
from app.core.config import settings
from app.models import Booking,SeatStatus,Showtime,Seat,BookingDetail
from app.models.sales import SalesConfiguration,SalesGate
from app.schemas.sales import SalesSnapshot
from app.services import sales_service as sales
from app.repositories.seat_repo import SeatRepository
from app.repositories.booking_repo import BookingRepository
from app.repositories.payment_repo import PaymentRepository
from app.services.booking_service import BookingService
from app.services.payment_service import PaymentService
from app.schemas.booking import BookingCreateRequest


def payload(**changes):
    body=dict(showtime_id=2000001,sales_version=1,catalog_binding_id=str(uuid4()),film_id=2000002,format_id=2000003,
        film=dict(id=2000002,title="Published film",catalog_version=1,format_ids=[2000003],format_name="2D"),
        room=dict(id=2000004,theater_id=2000005,name="Published room",capacity=10,status="ACTIVE"),
        theater=dict(id=2000005,name="Published theater",address="Test",city="Test"),
        show_date=date.today()+timedelta(days=5),start_time=time(18),end_time=time(20),status="ACTIVE",seat_count=1,
        seats=[dict(id=2000006,seat_name="A1",seat_type_id=2000007,seat_type="Standard",price="75000.00",status="ACTIVE")])
    return SalesSnapshot.model_validate({**body,**changes})


@pytest.fixture
def published(pg,catalog,monkeypatch):
    item=payload()
    sales.close(pg,item.showtime_id,1)
    sales.install(pg,item,item.digest(),2)
    sales.open_sales(pg,item.showtime_id,1,item.digest(),3)
    pg.execute(text("UPDATE domain_ownership SET owner='service' WHERE domain='cinema'")); pg.commit()
    monkeypatch.setattr(settings,"CINEMA_STORAGE_OWNER","service")
    monkeypatch.setattr("app.services.seat_service.SeatLockManager.get_all_locks_for_showtime",lambda *a:[])
    monkeypatch.setattr("app.services.seat_service.SeatLockManager.lock_seat",lambda **kw:True)
    return item


def test_protocol_rejects_incomplete_checksum_mutation_and_stale_commands(pg):
    item=payload()
    with pytest.raises(ValidationError): payload(seat_count=2)
    sales.close(pg,item.showtime_id,1)
    with pytest.raises(HTTPException): sales.install(pg,item,"a"*64,2)
    pg.rollback()
    sales.install(pg,item,item.digest(),2)
    assert sales.install(pg,item,item.digest(),2)["acknowledged"]
    sales.open_sales(pg,item.showtime_id,1,item.digest(),3)
    sales.close(pg,item.showtime_id,4)
    with pytest.raises(HTTPException): sales.open_sales(pg,item.showtime_id,1,item.digest(),3)
    pg.rollback()
    changed=item.model_copy(deep=True); changed.seats[0].price=Decimal("90000.00")
    with pytest.raises(HTTPException): sales.install(pg,changed,changed.digest(),5)
    pg.rollback()
    assert not pg.get(SalesGate,item.showtime_id).is_open
    with pytest.raises(DBAPIError):
        with pg.begin_nested(): pg.execute(text("UPDATE booking_sales_configurations SET digest='changed' WHERE showtime_id=:id"),{"id":item.showtime_id})


def test_external_show_and_seat_checkout_during_close_keeps_price_and_payment_history(pg,catalog,published,provider,monkeypatch):
    item=published; user=catalog["user"].id; seat=item.seats[0].id
    assert pg.get(Showtime,item.showtime_id) is None and pg.get(Seat,seat) is None
    queries=[]
    def watch(conn,cursor,statement,*args): queries.append(statement.lower())
    event.listen(pg.bind,"before_cursor_execute",watch)
    try:
        SeatRepository.hold_seat_optimistic(pg,item.showtime_id,seat,user); pg.commit()
        sales.close(pg,item.showtime_id,4)
        with pytest.raises(HTTPException): SeatRepository.hold_seat_optimistic(pg,item.showtime_id,seat,user)
        pg.rollback()
        request=BookingCreateRequest(userId=user,showtimeId=item.showtime_id,totalAmount=75000,paymentMethod="VNPAY",seats=[dict(seat_id=seat,price=1)])
        created=BookingService.create_booking(pg,request,user)
        booking=pg.get(Booking,created.bookingId)
        assert booking.sales_version==1 and booking.total_amount==75000
        update=item.model_copy(deep=True); update.sales_version=2; update.seats[0].price=Decimal("90000.00")
        with pytest.raises(HTTPException): sales.install(pg,update,update.digest(),5)
        pg.rollback()
        attempt=PaymentRepository.create_attempt(pg,booking)
        monkeypatch.setattr("app.services.cinema_remote.call",lambda *a,**k:pytest.fail("Callback/history cannot require Cinema availability"))
        result=PaymentService.confirm_vnpay_payment(pg,booking.id,"00",provider_params(attempt))
        assert result["status"]=="success"
        sales.install(pg,update,update.digest(),5)
        sales.open_sales(pg,item.showtime_id,2,update.digest(),6)
        detail=BookingRepository.get_booking_with_details(pg,booking.id)
        assert detail["seats"][0]["price"]==75000 and detail["filmTitle"]=="Published film"
        assert pg.get(SalesConfiguration,(item.showtime_id,2)).snapshot["seats"][0]["price"]=="90000.00"
        assert PaymentService.confirm_vnpay_payment(pg,booking.id,"00",provider_params(attempt))["status"]=="success"
        from app.services.seat_service import SeatService
        assert SeatService.get_seats_by_showtime(pg,item.showtime_id)[0]["status"]=="BOOKED"
    finally: event.remove(pg.bind,"before_cursor_execute",watch)
    import re
    assert not any(re.search(r"(?:from|join)\s+(?:theaters|cinema_rooms|showtimes|seats|seat_types)\b",q) for q in queries)


def test_expired_old_payment_cannot_consume_new_version_hold(pg,catalog,published,provider):
    item=published; user=catalog["user"].id; seat=item.seats[0].id
    hold=SeatRepository.hold_seat_optimistic(pg,item.showtime_id,seat,user); pg.commit()
    request=BookingCreateRequest(userId=user,showtimeId=item.showtime_id,totalAmount=75000,paymentMethod="VNPAY",seats=[dict(seat_id=seat,price=1)])
    created=BookingService.create_booking(pg,request,user); booking=pg.get(Booking,created.bookingId)
    attempt=PaymentRepository.create_attempt(pg,booking)
    booking.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
    # Simulate expiry cleanup releasing the old hold, then a new version hold.
    SeatRepository.release_seat_optimistic(pg,item.showtime_id,seat,user,sales_version=1)
    pg.add(booking); pg.commit()
    sales.close(pg,item.showtime_id,4)
    update=item.model_copy(deep=True); update.sales_version=2; update.seats[0].price=Decimal("90000.00")
    sales.install(pg,update,update.digest(),5); sales.open_sales(pg,item.showtime_id,2,update.digest(),6)
    SeatRepository.hold_seat_optimistic(pg,item.showtime_id,seat,user); pg.commit()
    assert PaymentService.confirm_vnpay_payment(pg,booking.id,"00",provider_params(attempt))["status"]=="failed"
    current=SeatRepository.get_seat_status(pg,item.showtime_id,seat)
    assert current.status=="HOLD" and current.sales_version==2
    assert not SeatRepository.release_seat_optimistic(pg,item.showtime_id,seat,user,sales_version=1)


def test_raw_legacy_writer_stays_fenced_after_environment_reset(pg,catalog,published,monkeypatch):
    monkeypatch.setattr(settings,"CINEMA_STORAGE_OWNER","monolith")
    from app.utils.cinema_ownership import require_legacy_cinema_owner
    with pytest.raises(HTTPException): require_legacy_cinema_owner(pg)
    with pytest.raises(DBAPIError):
        with pg.begin_nested(): pg.execute(text("UPDATE seats SET seat_name=seat_name WHERE id=:id"),{"id":catalog["seat"].id})
