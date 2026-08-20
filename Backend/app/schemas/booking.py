from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class SeatBookingRequest(BaseModel):
    """Thông tin ghế trong booking request"""
    seat_id: int
    price: float


class BookingCreateRequest(BaseModel):
    """Request tạo booking mới"""
    userId: int = Field(..., alias="userId", description="ID người dùng")
    showtimeId: int = Field(..., alias="showtimeId", description="ID suất chiếu")
    totalAmount: float = Field(..., alias="totalAmount", description="Tổng tiền")
    paymentMethod: str = Field(..., alias="paymentMethod", description="Phương thức thanh toán")
    seats: List[SeatBookingRequest] = Field(..., description="Danh sách ghế đặt")

    class Config:
        populate_by_name = True


class BookingResponse(BaseModel):
    """Response sau khi tạo booking"""
    bookingId: int = Field(..., alias="bookingId")
    userId: int = Field(..., alias="userId")
    showtimeId: int = Field(..., alias="showtimeId")
    bookingDate: datetime = Field(..., alias="bookingDate")
    totalAmount: float = Field(..., alias="totalAmount")
    paymentMethod: str = Field(..., alias="paymentMethod")
    paymentStatus: str = Field(..., alias="paymentStatus")
    bookingStatus: str = Field(..., alias="bookingStatus")
    seats: List[dict]

    class Config:
        populate_by_name = True
        from_attributes = True


class BookingDetailResponse(BaseModel):
    """Chi tiết booking"""
    id: int
    bookingId: int = Field(..., alias="bookingId")
    userId: int = Field(..., alias="userId")
    showtimeId: int = Field(..., alias="showtimeId")
    bookingDate: datetime = Field(..., alias="bookingDate")
    totalAmount: float = Field(..., alias="totalAmount")
    paymentMethod: str = Field(..., alias="paymentMethod")
    paymentStatus: str = Field(..., alias="paymentStatus")
    bookingStatus: str = Field(..., alias="bookingStatus")
    
    # Thông tin phim & suất chiếu
    filmTitle: Optional[str] = Field(None, alias="filmTitle")
    theaterName: Optional[str] = Field(None, alias="theaterName")
    roomName: Optional[str] = Field(None, alias="roomName")
    showDate: Optional[str] = Field(None, alias="showDate")
    startTime: Optional[str] = Field(None, alias="startTime")
    
    # Danh sách ghế đã đặt
    seats: List[dict]

    class Config:
        populate_by_name = True
        from_attributes = True
