from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List


class Seat(SQLModel, table=True):
    __tablename__ = "seats"

    id: Optional[int] = Field(default=None, primary_key=True)

    room_id: int = Field(foreign_key="cinema_rooms.id", index=True)
    seat_type_id: int = Field(foreign_key="seat_types.id", index=True)
    seat_name: str = Field(max_length=10)

    # Relationships
    room: "CinemaRoom" = Relationship(back_populates="seats")
    seat_type_rel: "SeatType" = Relationship(back_populates="seats")
    booking_details: List["BookingDetail"] = Relationship(back_populates="seat")
    seat_statuses: List["SeatStatus"] = Relationship(back_populates="seat")
