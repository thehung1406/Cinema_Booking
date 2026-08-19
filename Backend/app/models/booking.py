from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Numeric


class Booking(SQLModel, table=True):
    __tablename__ = "bookings"

    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="users.id", index=True)
    showtime_id: int = Field(foreign_key="showtimes.id", index=True)

    booking_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))

    payment_method: Optional[str] = Field(default=None, max_length=50)
    payment_status: str = Field(default="PENDING", max_length=20)
    booking_status: str = Field(default="PENDING", max_length=20)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ...existing code...
    user: "User" = Relationship(back_populates="bookings")
    showtime: "Showtime" = Relationship(back_populates="bookings")
    booked_seats: List["BookingDetail"] = Relationship(
        back_populates="booking"
    )
