from sqlmodel import SQLModel
from datetime import time, date
from typing import Optional


class ShowtimeRead(SQLModel):
    id: int
    room_id: int
    film_id: int
    show_date: date
    start_time: time
    end_time: time
    format: str
    status: str


class ShowtimeDetailRead(SQLModel):
    """Schema cho chi tiết suất chiếu với đầy đủ thông tin phim, rạp, phòng"""
    id: int
    show_date: date
    start_time: time
    end_time: time
    format: str
    status: str
    
    # Thông tin phim
    film_id: int
    film_title: str
    image: Optional[str] = None
    duration: Optional[str] = None 
    language: Optional[str] = None
    subtitle: Optional[str] = None
    
    # Thông tin rạp và phòng
    room_id: int
    room_name: str
    theater_id: int
    theater_name: str
    theater_address: Optional[str] = None