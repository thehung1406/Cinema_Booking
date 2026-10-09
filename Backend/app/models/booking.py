from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Numeric, DateTime, CheckConstraint, Index, String, text


class Booking(SQLModel, table=True):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("total_amount > 0", name="ck_booking_total_positive"),
        Index("ix_bookings_user_date", "user_id", text("booking_date DESC")),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    showtime_id: int = Field(foreign_key="showtimes.id", ondelete="RESTRICT", index=True)

    booking_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))
    total_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))

    payment_method: Optional[str] = Field(default=None, max_length=50)
    payment_status: str = Field(default="PENDING", sa_column=Column(String(20), nullable=False, server_default="PENDING"))
    booking_status: str = Field(default="PENDING", sa_column=Column(String(20), nullable=False, server_default="PENDING"))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))
    expires_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))

    # ...existing code...
    user: "User" = Relationship(back_populates="bookings")
    showtime: "Showtime" = Relationship(back_populates="bookings")
    booked_seats: List["BookingDetail"] = Relationship(
        back_populates="booking"
    )
