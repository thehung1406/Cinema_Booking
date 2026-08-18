from sqlmodel import SQLModel
from typing import Optional


class CinemaRoomRead(SQLModel):
    id: int
    theater_id: int
    name: str
    capacity: int
    room_type: Optional[str]
