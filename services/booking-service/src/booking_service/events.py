"""Transactional confirmation events: public facts and separate private email snapshot."""

import json
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

from .booking_repo import BookingRepository
from cinema_platform.events import EventEnvelope
from cinema_platform.outbox import enqueue


class ConfirmedData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    booking_id: int = Field(gt=0)
    payment_id: int = Field(gt=0)
    showtime_id: int = Field(gt=0)
    film_id: int = Field(gt=0)
    theater_id: int = Field(gt=0)
    show_date: str
    total_amount: Decimal = Field(gt=0)
    currency: str = Field(pattern="^VND$")
    seat_count: int = Field(gt=0)
    film_title: str
    theater_name: str


def booking_confirmed(db, booking, payment_id, *, include_public=True):
    detail = BookingRepository.get_booking_with_details(db, booking.id)
    if detail is None:
        raise ValueError("Confirmed booking snapshot is unavailable")
    from .sales import configuration
    from types import SimpleNamespace
    show=configuration(db,booking.showtime_id,booking.sales_version)
    room=SimpleNamespace(theater_id=show.theater_id)
    public = {
        "booking_id": booking.id, "payment_id": payment_id,
        "showtime_id": booking.showtime_id, "film_id": show.film_id,
        "theater_id": room.theater_id, "show_date": str(show.show_date),
        "total_amount": str(booking.total_amount), "currency": "VND",
        "seat_count": len(detail["seats"]), "film_title": detail["filmTitle"],
        "theater_name": detail["theaterName"],
    }

    def event(kind, data):
        return EventEnvelope(
            event_id=uuid5(NAMESPACE_URL, f"cinema:booking:{booking.id}:{kind}"),
            event_type=kind, producer="booking", aggregate_id=f"booking:{booking.id}",
            aggregate_version=1, correlation_id=f"booking:{booking.id}", data=data,
        )

    if include_public:
        enqueue(db, event("BookingConfirmed.v1", ConfirmedData.model_validate(public).model_dump(mode="json")), "public")
    if detail.get("email"):
        allowed = {key: detail.get(key) for key in (
            "bookingId", "fullName", "filmTitle", "theaterName", "roomName", "showDate",
            "startTime", "totalAmount", "seats", "foodItems",
        )}
        # JSON money values are strings, never binary floats. No phone/password/token in payload.
        snapshot = json.loads(json.dumps(allowed, default=str))
        enqueue(db, event("BookingConfirmationEmailRequested.v1", {
            "to_email": detail["email"], "booking_detail": snapshot,
        }), "notification")


def checkout_event(db,booking,kind):
    from .checkout import require_checkout
    checkout=require_checkout(db,booking)
    data=dict(booking_id=booking.id,booking_version=checkout.booking_version,reservation_id=checkout.reservation_id,
        amount=str(checkout.amount),currency=checkout.currency,deadline=checkout.deadline.isoformat(),showtime_id=booking.showtime_id,sales_version=booking.sales_version)
    enqueue(db,EventEnvelope(event_id=uuid5(NAMESPACE_URL,f"cinema:booking:{booking.id}:{kind}"),event_type=kind,producer="booking",aggregate_id=f"booking:{booking.id}",aggregate_version=checkout.booking_version,correlation_id=f"booking:{booking.id}",data=data),"public")
