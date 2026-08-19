from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from decimal import Decimal
from sqlalchemy import Column, Numeric


class BookingDetail(SQLModel, table=True):
    __tablename__ = "booking_details"

    id: Optional[int] = Field(default=None, primary_key=True)

    booking_id: int = Field(foreign_key="bookings.id", index=True)
    seat_id: int = Field(foreign_key="seats.id", index=True)

    price: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))

    # Relationships
    booking: "Booking" = Relationship(back_populates="booked_seats")
    seat: "Seat" = Relationship(back_populates="booking_details")

