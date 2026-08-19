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
    bookingId: Optional[str] = Field(None, alias="bookingId")
    vnp_TxnRef: Optional[str] = Field(None, alias="vnp_TxnRef")
    vnp_ResponseCode: str = Field(..., alias="vnp_ResponseCode")
    vnp_Amount: Optional[str] = Field(None, alias="vnp_Amount")
    vnp_BankCode: Optional[str] = Field(None, alias="vnp_BankCode")
    vnp_BankTranNo: Optional[str] = Field(None, alias="vnp_BankTranNo")
    vnp_CardType: Optional[str] = Field(None, alias="vnp_CardType")
    vnp_OrderInfo: Optional[str] = Field(None, alias="vnp_OrderInfo")
    vnp_PayDate: Optional[str] = Field(None, alias="vnp_PayDate")
    vnp_TransactionNo: Optional[str] = Field(None, alias="vnp_TransactionNo")
    vnp_TransactionStatus: Optional[str] = Field(None, alias="vnp_TransactionStatus")
    vnp_SecureHash: str = Field(..., alias="vnp_SecureHash")
    vnp_SecureHashType: Optional[str] = Field(None, alias="vnp_SecureHashType")
    
    class Config:
        populate_by_name = True


class PaymentConfirmResponse(BaseModel):
    """Response sau khi xác nhận thanh toán"""
    status: str  # success | failed
    booking: Optional[dict] = None
    message: str
