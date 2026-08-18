from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List



class CinemaRoom(SQLModel, table=True):
    __tablename__ = "cinema_rooms"

    id: Optional[int] = Field(default=None, primary_key=True)

    theater_id: int = Field(foreign_key="theaters.id", index=True)
    name: str = Field(max_length=50)
    capacity: int
    room_type: Optional[str] = Field(default=None, max_length=50)

    # Relationships
    theater: "Theater" = Relationship(back_populates="cinema_rooms")
    showtimes: List["Showtime"] = Relationship(back_populates="room")
    seats: List["Seat"] = Relationship(back_populates="room")
    seat_types: List["SeatType"] = Relationship(back_populates="room")

