from fastapi import HTTPException
from sqlmodel import select
from .models import Booking,Reservation
from .sales import gate
from .history import booking_detail,booking_list

class BookingRepository:
    @staticmethod
    def get_booking_by_id(db,booking_id,for_update=False):
        booking=db.get(Booking,booking_id)
        if booking is None: return None
        if for_update:
            gate(db,booking.showtime_id,lock=True)
            db.exec(select(Reservation).where(Reservation.id==booking.reservation_id).with_for_update().execution_options(populate_existing=True)).first()
            booking=db.exec(select(Booking).where(Booking.id==booking_id).with_for_update().execution_options(populate_existing=True)).one()
        return booking
    @staticmethod
    def get_booking_with_details(db,booking_id):
        booking=db.get(Booking,booking_id)
        return booking_detail(db,booking) if booking else None
    @staticmethod
    def get_user_bookings_with_details(db,user_id,skip=0,limit=50):
        bookings=db.exec(select(Booking).where(Booking.user_id==user_id).order_by(Booking.booking_date.desc(),Booking.id.desc()).offset(skip).limit(limit)).all()
        return booking_list(db,bookings)
