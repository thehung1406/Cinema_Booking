from pydantic import BaseModel, ConfigDict

class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)



from typing import Optional


class TheaterRead(ReadModel):
    id: int
    name: str
    address: str
    city: str
    rating: Optional[float] = None
    image: Optional[str] = None
    technologies: Optional[dict] = None
    special: Optional[str] = None


from typing import Optional


class CinemaRoomRead(ReadModel):
    id: int
    theater_id: int
    name: str
    capacity: int
    room_type: Optional[str]


from datetime import time, date
from typing import Optional


class ShowtimeRead(ReadModel):
    id: int
    room_id: int
    film_id: int
    show_date: date
    start_time: time
    end_time: time
    format: str
    status: str


class ShowtimeDetailRead(ReadModel):
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
from typing import Optional
from decimal import Decimal
from pydantic import Field


class SeatTypeRead(ReadModel):
    """Response cho SeatType"""
    id: int
    room_id: int
    name: str
    base_price: float

    class Config:
        from_attributes = True


class SeatTypeCreate(ReadModel):
    """Request tạo SeatType mới"""
    room_id: int = Field(..., gt=0, description="ID phòng chiếu")
    name: str = Field(..., max_length=30, description="Tên loại ghế (VIP, Standard...)")
    base_price: float = Field(..., gt=0, description="Giá mặc định")


class SeatTypeUpdatePrice(ReadModel):
    """Request cập nhật giá SeatType"""
    base_price: float = Field(..., gt=0, description="Giá mới")
