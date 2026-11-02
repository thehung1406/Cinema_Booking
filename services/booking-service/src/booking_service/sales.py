from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select, func, and_, or_
from .models.sales import SalesConfiguration, SalesGate
from .models import Booking, BookingDetail, SeatStatus
from .schemas.sales import SalesSnapshot


def gate(db, showtime_id, *, lock=False, create=False):
    query = select(SalesGate).where(SalesGate.showtime_id == showtime_id)
    if lock: query = query.with_for_update().execution_options(populate_existing=True)
    row = db.execute(query).scalar_one_or_none()
    if row is None and create:
        # PostgreSQL serializes competing first commands for the same showtime.
        from sqlalchemy import text
        db.execute(text("SELECT pg_advisory_xact_lock(7810,:id)"), {"id": showtime_id})
        row = db.execute(query).scalar_one_or_none()
        if row is None:
            row = SalesGate(showtime_id=showtime_id, epoch=0, action="INIT", is_open=False)
            db.add(row); db.flush()
    if row is None: raise HTTPException(409, "Suất chưa có cấu hình bán vé đã xác nhận")
    return row


def configuration(db, showtime_id, version=None, *, lock=False, require_open=False):
    row = gate(db, showtime_id, lock=lock)
    if require_open and not row.is_open: raise HTTPException(409, "Suất đang đóng nhận giữ ghế mới")
    version = version if version is not None else row.sales_version
    config = db.get(SalesConfiguration, (showtime_id, version)) if version else None
    if config is None: raise HTTPException(409, "Thiếu phiên bản bán vé đã xác nhận")
    return config


def current_query():
    from sqlmodel import select as model_select
    return model_select(SalesConfiguration).join(SalesGate, and_(SalesGate.showtime_id == SalesConfiguration.showtime_id,
        SalesGate.sales_version == SalesConfiguration.sales_version))


def future_query(film_id=None, theater_id=None, show_date=None, evening=False):
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    query = current_query().where(SalesGate.is_open.is_(True), SalesConfiguration.status == "ACTIVE",
        or_(SalesConfiguration.show_date > now.date(), and_(SalesConfiguration.show_date == now.date(),
            SalesConfiguration.start_time > now.time().replace(tzinfo=None))))
    if film_id is not None: query = query.where(SalesConfiguration.film_id == film_id)
    if theater_id is not None: query = query.where(SalesConfiguration.theater_id == theater_id)
    if show_date is not None: query = query.where(SalesConfiguration.show_date == show_date)
    if evening:
        from datetime import time
        query = query.where(SalesConfiguration.start_time >= time(18))
    return query.order_by(SalesConfiguration.show_date, SalesConfiguration.start_time, SalesConfiguration.showtime_id)


def seat_rows(config):
    from decimal import Decimal
    rows = []
    for seat in config.snapshot["seats"]:
        rows.append((SimpleNamespace(id=seat["id"], seat_name=seat["seat_name"], room_id=config.room_id,
            seat_type_id=seat["seat_type_id"], status=seat["status"]),
            SimpleNamespace(id=seat["seat_type_id"], room_id=config.room_id, name=seat["seat_type"], base_price=Decimal(seat["price"]))))
    return rows


def stats(db, showtime_id, *, seat_id=None):
    now = datetime.now(timezone.utc)
    holds = select(func.count()).select_from(SeatStatus).where(SeatStatus.showtime_id == showtime_id,
        SeatStatus.status == "HOLD", SeatStatus.hold_expired_at > now)
    pending = select(func.count()).select_from(Booking).where(Booking.showtime_id == showtime_id,
        Booking.booking_status == "PENDING", or_(Booking.expires_at > now,
            and_(Booking.expires_at.is_(None), Booking.booking_date > now-timedelta(minutes=10))))
    history = select(func.count()).select_from(Booking).where(Booking.showtime_id == showtime_id)
    refs = select(func.count()).select_from(BookingDetail).join(Booking, Booking.id == BookingDetail.booking_id).where(Booking.showtime_id == showtime_id)
    if seat_id is not None: refs = refs.where(BookingDetail.seat_id == seat_id)
    booked = list(db.scalars(select(SeatStatus.seat_id).where(SeatStatus.showtime_id == showtime_id, SeatStatus.status == "BOOKED")))
    return dict(live_holds=db.scalar(holds), pending_bookings=db.scalar(pending), bookings=db.scalar(history), seat_references=db.scalar(refs), booked_seat_ids=booked)


def command(row, epoch, action):
    if epoch < row.epoch or (epoch == row.epoch and row.action != action):
        raise HTTPException(409, "Lệnh bán vé cũ đã bị thay thế")
    repeated = epoch == row.epoch
    if not repeated: row.epoch, row.action = epoch, action
    return repeated


def close(db, showtime_id, epoch):
    row = gate(db, showtime_id, lock=True, create=True)
    command(row, epoch, "CLOSE")
    row.is_open = False
    db.commit()
    return {"epoch": row.epoch, "is_open": False, "sales_version": row.sales_version}


def install(db, snapshot: SalesSnapshot, digest, epoch):
    if snapshot.digest() != digest: raise HTTPException(409, "Checksum cấu hình bán vé không khớp")
    row = gate(db, snapshot.showtime_id, lock=True, create=True)
    repeated = command(row, epoch, "IMPORT")
    if row.is_open: raise HTTPException(409, "Phải đóng bán trước khi thay cấu hình")
    existing = db.get(SalesConfiguration, (snapshot.showtime_id, snapshot.sales_version))
    if repeated and (row.sales_version != snapshot.sales_version or existing is None or existing.digest != digest):
        raise HTTPException(409, "Không thể tái sử dụng lệnh cho cấu hình khác")
    if existing and existing.digest != digest: raise HTTPException(409, "Không thể thay nội dung phiên bản đã công bố")
    if row.sales_version and snapshot.sales_version < row.sales_version: raise HTTPException(409, "Phiên bản bán vé đã cũ")
    pending = stats(db, snapshot.showtime_id)
    if not repeated and row.sales_version and (pending["live_holds"] or pending["pending_bookings"]):
        raise HTTPException(409, "Còn hold hoặc đơn đang xử lý")
    if row.sales_version and snapshot.sales_version != row.sales_version:
        old = db.get(SalesConfiguration, (snapshot.showtime_id, row.sales_version))
        if pending["bookings"]:
            old_facts = old.snapshot
            if any(old_facts[key] != snapshot.model_dump(mode="json")[key] for key in ("film_id", "format_id", "show_date", "start_time", "end_time")) or old.room_id != snapshot.room.id:
                raise HTTPException(409, "Lịch đã có đơn; phải giữ nguyên lịch sử")
        occupied = db.scalars(select(SeatStatus.seat_id).where(SeatStatus.showtime_id == snapshot.showtime_id, SeatStatus.status == "BOOKED")).all()
        old_seats = {seat["id"]: seat for seat in old.snapshot["seats"]}
        new_seats = {seat.id: seat for seat in snapshot.seats}
        for seat_id in occupied:
            seat = new_seats.get(seat_id)
            if seat is None or seat.status != "ACTIVE" or seat.seat_name != old_seats[seat_id]["seat_name"] or seat.seat_type_id != old_seats[seat_id]["seat_type_id"]:
                raise HTTPException(409, "Không thể thay ghế đã bán")
    if existing is None:
        db.add(SalesConfiguration(showtime_id=snapshot.showtime_id, sales_version=snapshot.sales_version, digest=digest,
            film_id=snapshot.film_id, room_id=snapshot.room.id, theater_id=snapshot.theater.id,
            show_date=snapshot.show_date, start_time=snapshot.start_time, end_time=snapshot.end_time,
            status=snapshot.status, snapshot=snapshot.model_dump(mode="json")))
        db.flush()
    row.sales_version = snapshot.sales_version
    db.commit()
    return {"showtime_id": snapshot.showtime_id, "sales_version": snapshot.sales_version, "digest": digest, "acknowledged": True, "epoch": row.epoch}


def open_sales(db, showtime_id, version, digest, epoch):
    row = gate(db, showtime_id, lock=True)
    command(row, epoch, "OPEN")
    config = db.get(SalesConfiguration, (showtime_id, version))
    if config is None or row.sales_version != version or config.digest != digest:
        raise HTTPException(409, "Chưa nhận đủ và xác nhận phiên bản bán vé")
    if config.status != "ACTIVE" or config.snapshot["room"]["status"] != "ACTIVE":
        raise HTTPException(409, "Cấu hình không thể mở bán")
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).replace(tzinfo=None)
    if datetime.combine(config.show_date, config.start_time) <= now or not any(s["status"] == "ACTIVE" for s in config.snapshot["seats"]):
        raise HTTPException(409, "Suất đã bắt đầu hoặc chưa có ghế bán")
    row.is_open = True
    db.commit()
    return {"epoch": row.epoch, "is_open": True, "sales_version": version, "digest": digest}
