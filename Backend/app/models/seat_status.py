from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Index, String, Integer, text


class SeatStatus(SQLModel, table=True):
    __tablename__ = "seat_status"

    __table_args__ = (
        UniqueConstraint("showtime_id", "seat_id", name="uq_seat_showtime"),
        Index("ix_seat_status_showtime_status", "showtime_id", "status"),
        Index("ix_seat_status_hold_expired", "hold_expired_at", postgresql_where=text("status = 'HOLD' AND hold_expired_at IS NOT NULL")),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    seat_id: int = Field(foreign_key="seats.id", ondelete="RESTRICT", index=True)
    showtime_id: int = Field(foreign_key="showtimes.id", ondelete="RESTRICT", index=True)

    status: str = Field(default="AVAILABLE", sa_column=Column(String(20), nullable=False, server_default="AVAILABLE"))
    # AVAILABLE | HOLD | BOOKED

    version: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))

    hold_by_user_id: Optional[int] = Field(
        default=None, foreign_key="users.id", ondelete="SET NULL"
    )
    hold_expired_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    # Relationships
    seat: "Seat" = Relationship(back_populates="seat_statuses")
    showtime: "Showtime" = Relationship(back_populates="seat_statuses")
    hold_user: Optional["User"] = Relationship(back_populates="seat_statuses")

