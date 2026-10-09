from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import CheckConstraint, Column, DateTime, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


class Payment(SQLModel, table=True):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("provider", "transaction_ref", name="uq_payment_provider_transaction"),
        CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        CheckConstraint("status IN ('PENDING','PAID','FAILED','CANCELLED')", name="ck_payment_status"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    booking_id: int = Field(foreign_key="bookings.id", ondelete="RESTRICT", index=True)
    provider: str = Field(max_length=30)
    payment_method: str = Field(max_length=50)
    merchant_ref: str = Field(max_length=100, unique=True)
    transaction_ref: Optional[str] = Field(default=None, max_length=100)
    amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    currency: str = Field(default="VND", max_length=3)
    status: str = Field(default="PENDING", max_length=20)
    paid_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))
