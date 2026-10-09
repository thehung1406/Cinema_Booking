from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import date, time
from enum import Enum
from sqlalchemy import ForeignKeyConstraint, Index, Column, String


class ShowtimeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class Showtime(SQLModel, table=True):
    __tablename__ = "showtimes"
    __table_args__ = (ForeignKeyConstraint(
        ["film_id", "format_id"], ["film_formats.film_id", "film_formats.format_id"],
        name="fk_showtime_film_format", ondelete="RESTRICT"),
        Index("ix_showtimes_film_date_status", "film_id", "show_date", "status"))

    id: Optional[int] = Field(default=None, primary_key=True)

    film_id: int = Field(foreign_key="films.id", ondelete="RESTRICT", index=True)
    room_id: int = Field(foreign_key="cinema_rooms.id", ondelete="RESTRICT", index=True)

    show_date: date
    start_time: time
    end_time: time

    format_id: int = Field(foreign_key="formats.id", ondelete="RESTRICT", index=True)
    status: ShowtimeStatus = Field(default=ShowtimeStatus.ACTIVE, sa_column=Column(String(20), nullable=False, server_default="ACTIVE"))

    # Relationships
    film: "Film" = Relationship(back_populates="showtimes", sa_relationship_kwargs={"foreign_keys": "Showtime.film_id"})
    format_item: "Format" = Relationship(sa_relationship_kwargs={"lazy": "joined", "foreign_keys": "Showtime.format_id"})
    room: "CinemaRoom" = Relationship(back_populates="showtimes")
    bookings: List["Booking"] = Relationship(back_populates="showtime")
    seat_statuses: List["SeatStatus"] = Relationship(back_populates="showtime")

    @property
    def format(self) -> str:
        return self.format_item.name

