from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from decimal import Decimal
from sqlalchemy import Column, Numeric


class SeatType(SQLModel, table=True):
    __tablename__ = "seat_types"

    id: Optional[int] = Field(default=None, primary_key=True)

    room_id: int = Field(foreign_key="cinema_rooms.id", index=True)
    name: str = Field(max_length=30)  # "VIP", "Standard", "Couple"
    base_price: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))

    # Relationships
    room: "CinemaRoom" = Relationship(back_populates="seat_types")
    seats: List["Seat"] = Relationship(back_populates="seat_type_rel")
