from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import CheckConstraint, Column, DateTime
from sqlmodel import Field, SQLModel


class Ticket(SQLModel, table=True):
    __tablename__ = "tickets"
    __table_args__ = (CheckConstraint("status IN ('ISSUED','USED','CANCELLED')", name="ck_ticket_status"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    booking_detail_id: int = Field(foreign_key="booking_details.id", ondelete="RESTRICT", unique=True)
    ticket_code: str = Field(max_length=100, unique=True)
    status: str = Field(default="ISSUED", max_length=20)
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))
    used_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
