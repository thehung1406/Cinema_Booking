from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import date, time


class Showtime(SQLModel, table=True):
    __tablename__ = "showtimes"

    id: Optional[int] = Field(default=None, primary_key=True)

    film_id: int = Field(foreign_key="films.id", index=True)
    room_id: int = Field(foreign_key="cinema_rooms.id", index=True)

    show_date: date
    start_time: time
    end_time: time

    format: str = Field(max_length=20)
    status: str = Field(default="ACTIVE", max_length=20)

    # Relationships
    film: "Film" = Relationship(back_populates="showtimes")
    room: "CinemaRoom" = Relationship(back_populates="showtimes")
    bookings: List["Booking"] = Relationship(back_populates="showtime")
    seat_statuses: List["SeatStatus"] = Relationship(back_populates="showtime")

