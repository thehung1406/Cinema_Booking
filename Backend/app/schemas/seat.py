from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from app.utils.enum import SeatStatusEnum


class HoldSeatRequest(BaseModel):
    """Request để giữ ghế"""
    showtime_id: int = Field(..., description="ID suất chiếu", gt=0)
    seat_ids: List[int] = Field(..., min_length=1, description="Danh sách ID ghế cần giữ")


class ReleaseSeatRequest(BaseModel):
    """Request để hủy giữ ghế"""
    showtime_id: int = Field(..., description="ID suất chiếu", gt=0)
    seat_ids: List[int] = Field(..., min_length=1, description="Danh sách ID ghế cần hủy giữ")


class SeatStatusResponse(BaseModel):
    """Response trạng thái ghế"""
    seat_id: int
    seat_name: str
    seat_type: str
    price: float
    status: SeatStatusEnum
    hold_by_user_id: Optional[int] = None
    hold_expired_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HoldSeatResponse(BaseModel):
    """Response sau khi giữ ghế"""
    seat_id: int
    seat_name: str
    status: SeatStatusEnum
    hold_expired_at: datetime

    class Config:
        from_attributes = True


class SeatStatusRead(BaseModel):
    id: int
    seat_name: str
    seat_type: str
    price: float

