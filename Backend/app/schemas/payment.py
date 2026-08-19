from typing import Optional
from pydantic import BaseModel, Field


class VNPayURLRequest(BaseModel):
    """Request tạo URL thanh toán VNPay"""
    bookingId: int
    amount: float
    orderInfo: str
    returnUrl: str


class VNPayURLResponse(BaseModel):
    """Response chứa payment URL"""
    paymentUrl: str


class VNPayReturnRequest(BaseModel):
    """Request từ VNPay callback"""
    bookingId: str = Field(..., alias="bookingId")
    vnp_ResponseCode: str = Field(..., alias="vnp_ResponseCode")
    
    class Config:
        populate_by_name = True


class PaymentConfirmResponse(BaseModel):
    """Response sau khi xác nhận thanh toán"""
    status: str  # success | failed
    booking: Optional[dict] = None
    message: str
