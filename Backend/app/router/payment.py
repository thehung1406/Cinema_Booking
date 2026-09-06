from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session
import hashlib
import hmac
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging

from app.core.database import get_session
from app.core.config import settings
from app.models.user import User
from app.repositories.booking_repo import BookingRepository
from app.schemas.payment import (
    VNPayURLRequest, 
    VNPayURLResponse,
    VNPayReturnRequest, 
    PaymentConfirmResponse,
    VNPayIPNResponse
)
from app.services.payment_service import PaymentService
from app.utils.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payment", tags=["Payment"])


def verify_vnpay_signature(params: dict) -> bool:
    """
    Xác thực chữ ký HMAC-SHA512 của VNPay.
    Lọc bỏ vnp_SecureHash, vnp_SecureHashType và các giá trị rỗng/None.
    Sắp xếp các tham số theo thứ tự alphabet và băm dữ liệu với HASH_SECRET.
    """
    secure_hash = params.get("vnp_SecureHash")
    if not secure_hash:
        return False

    signed_params = {
        key: value
        for key, value in params.items()
        if key.startswith("vnp_")
        and key not in {"vnp_SecureHash", "vnp_SecureHashType"}
        and value is not None
        and str(value) != ""
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
    return hmac.compare_digest(expected_hash.lower(), str(secure_hash).lower())


@router.post("/vnpay-url", response_model=VNPayURLResponse)
def create_vnpay_url(
    request: VNPayURLRequest,
    http_request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Tạo URL thanh toán VNPay Sandbox với mã checksum HMAC-SHA512.
    Amount, order info và return URL được lấy/derive server-side từ booking.
    """
    booking = BookingRepository.get_booking_by_id(db=db, booking_id=request.bookingId)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking không tồn tại"
        )

    if booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thanh toán booking này"
        )

    if booking.payment_status != "PENDING" or booking.booking_status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking không còn ở trạng thái chờ thanh toán"
        )

    vnp_TmnCode = settings.TMN_CODE
    vnp_HashSecret = settings.HASH_SECRET
    vnp_Url = settings.VNPAY_URL
    
    # Đồng bộ với thời gian giữ ghế/booking pending 10 phút.
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    create_date = now.strftime('%Y%m%d%H%M%S')
    expire_date = (now + timedelta(minutes=10)).strftime('%Y%m%d%H%M%S')
    
    # VNPay yêu cầu amount là số nguyên (nhân 100 để đổi từ VND sang xu/đồng nhỏ nhất)
    vnp_amount = int(round(float(booking.total_amount) * 100))
    if vnp_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số tiền booking không hợp lệ"
        )
    
    # Lấy IP client
    client_ip = "127.0.0.1"
    if http_request.client and http_request.client.host:
        client_ip = http_request.client.host
    forwarded = http_request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    
    vnp_Params = {
        'vnp_Version': '2.1.0',
        'vnp_Command': 'pay',
        'vnp_TmnCode': vnp_TmnCode,
        'vnp_Amount': str(vnp_amount),
        'vnp_CurrCode': 'VND',
        'vnp_TxnRef': str(booking.id),
        'vnp_OrderInfo': f"Thanh toan ve phim booking {booking.id}",
        'vnp_OrderType': 'other',
        'vnp_Locale': 'vn',
        'vnp_ReturnUrl': f"{settings.FRONTEND_URL.rstrip('/')}/payment-result",
        'vnp_CreateDate': create_date,
        'vnp_ExpireDate': expire_date,
        'vnp_IpAddr': client_ip
    }
    
    # Sắp xếp params theo alphabet
    sorted_params = sorted(vnp_Params.items())
    
    # Tạo hash data - URL encode giá trị theo chuẩn VNPay
    hash_data = '&'.join([f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in sorted_params])
    
    # Tạo secure hash HMAC-SHA512
    secure_hash = hmac.new(
        vnp_HashSecret.encode('utf-8'),
        hash_data.encode('utf-8'),
        hashlib.sha512
    ).hexdigest()
    
    # URL chuyển hướng tới VNPay Sandbox
    payment_url = f"{vnp_Url}?{hash_data}&vnp_SecureHash={secure_hash}"
    logger.info(f"Generated VNPay URL for booking {request.bookingId}")
    
    return VNPayURLResponse(paymentUrl=payment_url)


@router.post("/vnpay-return", response_model=PaymentConfirmResponse)
def vnpay_return_post(
    payment_data: VNPayReturnRequest,
    db: Session = Depends(get_session)
):
    """
    Xác nhận giao dịch VNPay qua Return URL (POST từ Frontend)
    """
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
        vnp_response_code=payment_data.vnp_ResponseCode,
        vnp_params=params
    )
    
    return PaymentConfirmResponse(**result)


@router.get("/vnpay-return", response_model=PaymentConfirmResponse)
def vnpay_return_get(
    http_request: Request,
    db: Session = Depends(get_session)
):
    """
    Xác nhận giao dịch VNPay qua Return URL (GET trực tiếp)
    """
    params = dict(http_request.query_params)
    if not verify_vnpay_signature(params):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chữ ký VNPay không hợp lệ"
        )

    booking_ref = params.get("vnp_TxnRef")
    try:
        booking_id = int(booking_ref)
    except (TypeError, ValueError):
        return PaymentConfirmResponse(
            status="failed",
            booking=None,
            message="Booking ID không hợp lệ"
        )
    
    response_code = params.get("vnp_ResponseCode", "")
    result = PaymentService.confirm_vnpay_payment(
        db=db,
        booking_id=booking_id,
        vnp_response_code=response_code,
        vnp_params=params
    )
    
    return PaymentConfirmResponse(**result)


@router.get("/vnpay-ipn", response_model=VNPayIPNResponse)
def vnpay_ipn_get(
    http_request: Request,
    db: Session = Depends(get_session)
):
    """
    Webhook tiếp nhận Instant Payment Notification (IPN) từ VNPay Server (GET)
    """
    params = dict(http_request.query_params)
    result = PaymentService.process_vnpay_ipn(db=db, params=params)
    return VNPayIPNResponse(**result)


@router.post("/vnpay-ipn", response_model=VNPayIPNResponse)
async def vnpay_ipn_post(
    http_request: Request,
    db: Session = Depends(get_session)
):
    """
    Webhook tiếp nhận Instant Payment Notification (IPN) từ VNPay Server (POST)
    """
    params = dict(http_request.query_params)
    try:
        if "application/json" in http_request.headers.get("content-type", ""):
            body_params = await http_request.json()
            if isinstance(body_params, dict):
                params.update(body_params)
        else:
            form_params = await http_request.form()
            params.update(dict(form_params))
    except Exception as exc:
        logger.warning(f"Could not parse VNPay IPN POST body: {exc}")
    result = PaymentService.process_vnpay_ipn(db=db, params=params)
    return VNPayIPNResponse(**result)


@router.get("/status/{booking_id}")
def get_payment_status(
    booking_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Tra cứu trạng thái thanh toán của booking
    """
    return PaymentService.get_payment_status(
        db=db,
        booking_id=booking_id,
        user_id=current_user.id
    )
