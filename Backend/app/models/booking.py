from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Numeric, DateTime, CheckConstraint, Index, String, JSON, text


class Booking(SQLModel, table=True):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("total_amount > 0", name="ck_booking_total_positive"),
        Index("ix_bookings_user_date", "user_id", text("booking_date DESC")),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(index=True)
    customer_full_name: Optional[str] = Field(default=None, max_length=100)
    customer_email: Optional[str] = Field(default=None, max_length=100)
    customer_phone: Optional[str] = Field(default=None, max_length=15)
    catalog_film_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, server_default="{}"))
    sales_version: Optional[int] = None
    food_quote_id: Optional[str] = Field(default=None, max_length=36)
    food_quote_version: Optional[int] = None
    food_quote_expires_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    showtime_id: int = Field(index=True)

    booking_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))
    total_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))

    payment_method: Optional[str] = Field(default=None, max_length=50)
    payment_status: str = Field(default="PENDING", sa_column=Column(String(20), nullable=False, server_default="PENDING"))
    booking_status: str = Field(default="PENDING", sa_column=Column(String(20), nullable=False, server_default="PENDING"))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))
    expires_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))

    # ...existing code...
    booked_seats: List["BookingDetail"] = Relationship(
        back_populates="booking"
    )
