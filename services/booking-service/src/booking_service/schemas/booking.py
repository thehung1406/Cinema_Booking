from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal
from .food import FoodSelection, BookingFoodRead


class SeatBookingRequest(BaseModel):
    """Thông tin ghế trong booking request"""
    seat_id: int = Field(gt=0)
    price: float


class BookingCreateRequest(BaseModel):
    """Request tạo booking mới"""
    userId: int = Field(..., alias="userId", description="ID người dùng")
    showtimeId: int = Field(..., alias="showtimeId", description="ID suất chiếu")
    totalAmount: Decimal = Field(..., alias="totalAmount",gt=0,max_digits=12,decimal_places=2,description="Tổng tiền")
    paymentMethod: str = Field(...,alias="paymentMethod",min_length=1,max_length=50)
    seats: List[SeatBookingRequest] = Field(..., min_length=1, description="Danh sách ghế đặt")
    reservationId: Optional[str] = Field(default=None,max_length=36)
    foodItems: List[FoodSelection] = Field(default_factory=list, max_length=50)

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
    foodItems: List[BookingFoodRead] = Field(default_factory=list)

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
    filmImage: Optional[str] = Field(None, alias="filmImage")
    theaterName: Optional[str] = Field(None, alias="theaterName")
    roomName: Optional[str] = Field(None, alias="roomName")
    showDate: Optional[str] = Field(None, alias="showDate")
    startTime: Optional[str] = Field(None, alias="startTime")

    # Thông tin người dùng
    fullName: Optional[str] = Field(None, alias="fullName")
    email: Optional[str] = Field(None, alias="email")
    phone: Optional[str] = Field(None, alias="phone")

    # Danh sách ghế đã đặt
    seats: List[dict]
    foodItems: List[BookingFoodRead] = Field(default_factory=list)

    class Config:
        populate_by_name = True
        from_attributes = True


class BookingPaymentStatusUpdateRequest(BaseModel):
    """Request cập nhật trạng thái thanh toán của booking"""
    payment_status: str = Field(
        ...,
        description="Trạng thái thanh toán mới (FAILED hoặc CANCELLED)"
    )
