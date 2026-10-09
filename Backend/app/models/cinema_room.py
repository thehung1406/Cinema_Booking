from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from sqlalchemy import Column, DateTime



class CinemaRoom(SQLModel, table=True):
    __tablename__ = "cinema_rooms"

    id: Optional[int] = Field(default=None, primary_key=True)

    theater_id: int = Field(foreign_key="theaters.id", ondelete="RESTRICT", index=True)
    name: str = Field(max_length=50)
    capacity: int
    room_type: Optional[str] = Field(default=None, max_length=50)
    status: str = Field(default="ACTIVE", max_length=20)
    deleted_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))

    # Relationships
    theater: "Theater" = Relationship(back_populates="cinema_rooms")
    showtimes: List["Showtime"] = Relationship(back_populates="room")
    seats: List["Seat"] = Relationship(back_populates="room")
    seat_types: List["SeatType"] = Relationship(back_populates="room")
