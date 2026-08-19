from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field


class SeatTypeRead(BaseModel):
    """Response cho SeatType"""
    id: int
    room_id: int
    name: str
    base_price: float

    class Config:
        from_attributes = True


class SeatTypeCreate(BaseModel):
    """Request tạo SeatType mới"""
    room_id: int = Field(..., gt=0, description="ID phòng chiếu")
    name: str = Field(..., max_length=30, description="Tên loại ghế (VIP, Standard...)")
    base_price: float = Field(..., gt=0, description="Giá mặc định")


class SeatTypeUpdatePrice(BaseModel):
    """Request cập nhật giá SeatType"""
    base_price: float = Field(..., gt=0, description="Giá mới")
