from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
import hashlib
import hmac
import urllib.parse
from datetime import datetime

from app.core.database import get_session
from app.core.config import settings
from app.schemas.payment import (
    VNPayURLRequest, 
    VNPayURLResponse,
    VNPayReturnRequest, 
    PaymentConfirmResponse
)
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payment", tags=["Payment"])


def verify_vnpay_signature(params: dict) -> bool:
    secure_hash = params.get("vnp_SecureHash")
    if not secure_hash:
        return False

    signed_params = {
        key: value
        for key, value in params.items()
        if key.startswith("vnp_")
        and key not in {"vnp_SecureHash", "vnp_SecureHashType"}
        and value is not None
    }
    sorted_params = sorted(signed_params.items())
    hash_data = "&".join(
        f"{key}={urllib.parse.quote_plus(str(value))}"
        for key, value in sorted_params
    )
    expected_hash = hmac.new(
        settings.HASH_SECRET.encode("utf-8"),
        hash_data.encode("utf-8"),
        hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected_hash, secure_hash)


@router.post("/vnpay-url", response_model=VNPayURLResponse)
def create_vnpay_url(
    request: VNPayURLRequest,
    db: Session = Depends(get_session)
):
    """
    Tạo URL thanh toán VNPay Sandbox
    """
    # VNPay config từ .env
    vnp_TmnCode = settings.TMN_CODE
    vnp_HashSecret = settings.HASH_SECRET
    vnp_Url = settings.VNPAY_URL
    
    # Tạo các tham số
    create_date = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # VNPay yêu cầu amount là số nguyên (đã nhân 100 để chuyển từ đồng sang xu)
    vnp_amount = int(request.amount * 100) if request.amount < 1000000 else int(request.amount)
    
    vnp_Params = {
        'vnp_Version': '2.1.0',
        'vnp_Command': 'pay',
        'vnp_TmnCode': vnp_TmnCode,
        'vnp_Amount': str(vnp_amount),  # Phải là chuỗi số nguyên
        'vnp_CurrCode': 'VND',
        'vnp_TxnRef': str(request.bookingId),
        'vnp_OrderInfo': f"Thanh toan ve phim booking {request.bookingId}",  # Không dùng ký tự đặc biệt
        'vnp_OrderType': 'other',
        'vnp_Locale': 'vn',
        'vnp_ReturnUrl': request.returnUrl,
        'vnp_CreateDate': create_date,
        'vnp_IpAddr': '127.0.0.1'
    }
    
    # Sắp xếp params theo alphabet
    sorted_params = sorted(vnp_Params.items())
    
    # Tạo hash data - VNPay yêu cầu URL encode giá trị trước khi hash
    hash_data = '&'.join([f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in sorted_params])
    
    # Debug: In ra hash data để kiểm tra
    print("="*50)
    print("Hash Data:", hash_data)
    print("Hash Secret:", vnp_HashSecret)
    
    # Tạo secure hash
    secure_hash = hmac.new(
        vnp_HashSecret.encode('utf-8'),
        hash_data.encode('utf-8'),
        hashlib.sha512
    ).hexdigest()
    
    print("Secure Hash:", secure_hash)
    print("="*50)
    
    # Query string giống với hash_data
    query_string = hash_data
    
    # URL cuối cùng
    payment_url = f"{vnp_Url}?{query_string}&vnp_SecureHash={secure_hash}"
    
    return VNPayURLResponse(paymentUrl=payment_url)

@router.post("/vnpay-return", response_model=PaymentConfirmResponse)
def vnpay_return(
    payment_data: VNPayReturnRequest,
    db: Session = Depends(get_session)
):
    params = payment_data.model_dump(by_alias=True, exclude_none=True)
    if not verify_vnpay_signature(params):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chữ ký VNPay không hợp lệ"
        )

    booking_ref = payment_data.vnp_TxnRef or payment_data.bookingId
    try:
        booking_id = int(booking_ref)
    except (TypeError, ValueError):
        return PaymentConfirmResponse(
            status="failed",
            booking=None,
            message="Booking ID không hợp lệ"
        )
    
    result = PaymentService.confirm_vnpay_payment(
        db=db,
        booking_id=booking_id,
        vnp_response_code=payment_data.vnp_ResponseCode
    )
    
    return PaymentConfirmResponse(**result)


@router.get("/status/{booking_id}")
def get_payment_status(
    booking_id: int,
    db: Session = Depends(get_session)
):
    return PaymentService.get_payment_status(
        db=db,
        booking_id=booking_id
    )
