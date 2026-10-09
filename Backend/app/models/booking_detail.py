from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from decimal import Decimal
from sqlalchemy import Column, Numeric, UniqueConstraint, CheckConstraint


class BookingDetail(SQLModel, table=True):
    __tablename__ = "booking_details"
    __table_args__ = (
        UniqueConstraint("booking_id", "seat_id", name="uq_booking_detail_seat"),
        CheckConstraint("price >= 0", name="ck_booking_detail_price"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    booking_id: int = Field(foreign_key="bookings.id", ondelete="RESTRICT", index=True)
    seat_id: int = Field(foreign_key="seats.id", ondelete="RESTRICT", index=True)

    price: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))

    # Relationships
    booking: "Booking" = Relationship(back_populates="booked_seats")
    seat: "Seat" = Relationship(back_populates="booking_details")

