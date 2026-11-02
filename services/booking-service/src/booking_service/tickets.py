from datetime import datetime, timezone
from secrets import token_urlsafe
from fastapi import HTTPException
from sqlalchemy import update
from sqlmodel import Session, select
from .models import Booking, BookingDetail, Ticket


class TicketService:
    @staticmethod
    def issue_for_booking(db: Session, booking: Booking):
        """Runs in the same transaction as payment confirmation; caller locks booking."""
        if booking.payment_status != "PAID" or booking.booking_status != "CONFIRMED":
            raise HTTPException(409, "Chỉ phát hành vé cho đơn đã thanh toán")
        db.flush()
        details = db.exec(select(BookingDetail).where(BookingDetail.booking_id == booking.id)).all()
        existing = set(db.exec(select(Ticket.booking_detail_id).join(BookingDetail)
                              .where(BookingDetail.booking_id == booking.id)).all())
        for detail in details:
            if detail.id not in existing:
                db.add(Ticket(booking_detail_id=detail.id, ticket_code=token_urlsafe(32)))
        db.flush()

    @staticmethod
    def check_in(db: Session, ticket_code: str):
        from .booking_repo import BookingRepository
        booking_id=db.exec(select(Booking.id).join(BookingDetail,BookingDetail.booking_id==Booking.id).join(Ticket,Ticket.booking_detail_id==BookingDetail.id).where(Ticket.ticket_code==ticket_code)).first()
        if booking_id is None: raise HTTPException(404,"Vé không tồn tại")
        BookingRepository.get_booking_by_id(db,booking_id,for_update=True)
        result = db.exec(update(Ticket).where(Ticket.ticket_code == ticket_code,
                                             Ticket.status == "ISSUED")
                         .values(status="USED", used_at=datetime.now(timezone.utc)))
        if result.rowcount != 1:
            db.rollback()
            ticket = db.exec(select(Ticket).where(Ticket.ticket_code == ticket_code)).first()
            raise HTTPException(409 if ticket else 404, "Vé đã sử dụng, bị hủy hoặc không tồn tại")
        db.commit()
        return db.exec(select(Ticket).where(Ticket.ticket_code == ticket_code)).one()
