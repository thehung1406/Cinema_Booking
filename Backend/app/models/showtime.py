from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import date, time
from enum import Enum
from sqlalchemy import Index, Column, String, JSON


class ShowtimeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class Showtime(SQLModel, table=True):
    __tablename__ = "showtimes"
    __table_args__ = (Index("ix_showtimes_film_date_status", "film_id", "show_date", "status"),)

    id: Optional[int] = Field(default=None, primary_key=True)

    film_id: int = Field(index=True)
    room_id: int = Field(foreign_key="cinema_rooms.id", ondelete="RESTRICT", index=True)

    show_date: date
    start_time: time
    end_time: time

    format_id: int = Field(index=True)
    status: ShowtimeStatus = Field(default=ShowtimeStatus.ACTIVE, sa_column=Column(String(20), nullable=False, server_default="ACTIVE"))

    catalog_binding_id: Optional[str] = Field(default=None, max_length=36)
    catalog_film_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, server_default="{}"))

    # Relationships
    room: "CinemaRoom" = Relationship(back_populates="showtimes")

    @property
    def format(self) -> str:
        return self.catalog_film_snapshot.get("format_name", "")

