from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, select
from app.core.database import get_session
from app.models import Booking, BookingDetail, Ticket
from app.services.ticket_service import TicketService
from app.utils.dependencies import get_current_user, require_permission

router = APIRouter(prefix="/tickets", tags=["Tickets"])


class TicketRead(SQLModel):
    id: int
    booking_detail_id: int
    ticket_code: str
    status: str
    issued_at: datetime
    used_at: datetime | None


@router.get("/booking/{booking_id}", response_model=list[TicketRead])
def booking_tickets(booking_id: int, db: Session = Depends(get_session), user=Depends(get_current_user)):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(404, "Booking không tồn tại")
    if booking.user_id != user.id:
        raise HTTPException(403, "Bạn không có quyền xem vé này")
    return db.exec(select(Ticket).join(BookingDetail)
                   .where(BookingDetail.booking_id == booking_id).order_by(Ticket.id)).all()


@router.post("/{ticket_code}/check-in", response_model=TicketRead)
def check_in(ticket_code: str, db: Session = Depends(get_session),
             staff=Depends(require_permission("tickets.check_in"))):
    return TicketService.check_in(db, ticket_code)
