from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint
from typing import Optional
from datetime import datetime, timezone


class SeatStatus(SQLModel, table=True):
    __tablename__ = "seat_status"

    __table_args__ = (
        UniqueConstraint("showtime_id", "seat_id", name="uq_seat_showtime"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    seat_id: int = Field(foreign_key="seats.id", index=True)
    showtime_id: int = Field(foreign_key="showtimes.id", index=True)

    status: str = Field(default="AVAILABLE", max_length=20)
    # AVAILABLE | HOLD | BOOKED

    hold_by_user_id: Optional[int] = Field(
        default=None, foreign_key="users.id"
    )
    hold_expired_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    seat: "Seat" = Relationship(back_populates="seat_statuses")
    showtime: "Showtime" = Relationship(back_populates="seat_statuses")
    hold_user: Optional["User"] = Relationship(back_populates="seat_statuses")

