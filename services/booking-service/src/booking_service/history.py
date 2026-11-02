"""Booking-owned immutable publication facts; no Cinema ORM/API joins."""
from fastapi import HTTPException
from sqlmodel import select
from .models import BookingDetail
from .models.sales import SalesConfiguration
from .food import FoodService


def booking_detail(db, booking, *, config=None, details=None, foods=None):
    config = config or db.get(SalesConfiguration, (booking.showtime_id, booking.sales_version))
    if config is None: raise HTTPException(503, "Thiếu snapshot lịch sử bán vé")
    snapshot = config.snapshot
    seats = {seat["id"]: seat for seat in snapshot["seats"]}
    if details is None: details = db.exec(select(BookingDetail).where(BookingDetail.booking_id == booking.id).order_by(BookingDetail.id)).all()
    lines = []
    for row in details:
        seat = seats.get(row.seat_id)
        if seat is None: raise HTTPException(503, "Thiếu snapshot ghế đã đặt")
        lines.append(dict(seat_id=row.seat_id, seat_name=seat["seat_name"], seat_type=seat["seat_type"], price=row.price))
    film = booking.catalog_film_snapshot or snapshot["film"]
    return dict(id=booking.id, bookingId=booking.id, userId=booking.user_id, showtimeId=booking.showtime_id,
        bookingDate=booking.booking_date, totalAmount=booking.total_amount, paymentMethod=booking.payment_method,
        paymentStatus=booking.payment_status, bookingStatus=booking.booking_status,
        filmTitle=film["title"], filmImage=film.get("image"), theaterName=snapshot["theater"]["name"], roomName=snapshot["room"]["name"],
        showDate=snapshot["show_date"], startTime=snapshot["start_time"], fullName=booking.customer_full_name,
        email=booking.customer_email, phone=booking.customer_phone, seats=lines,
        foodItems=foods if foods is not None else FoodService.for_bookings(db, [booking.id]).get(booking.id, []))


def booking_list(db, bookings):
    if not bookings: return []
    from sqlalchemy import tuple_
    keys=[(b.showtime_id,b.sales_version) for b in bookings]
    configs={(c.showtime_id,c.sales_version):c for c in db.scalars(select(SalesConfiguration).where(tuple_(SalesConfiguration.showtime_id,SalesConfiguration.sales_version).in_(keys)))}
    ids=[b.id for b in bookings]
    details={i:[] for i in ids}
    for d in db.exec(select(BookingDetail).where(BookingDetail.booking_id.in_(ids)).order_by(BookingDetail.id)): details[d.booking_id].append(d)
    foods=FoodService.for_bookings(db,ids)
    return [booking_detail(db,b,config=configs.get((b.showtime_id,b.sales_version)),details=details[b.id],foods=foods.get(b.id,[])) for b in bookings]
