"""
Test suite kiem tra tinh nhat quan cua Payment & Booking Seat Lock (Issues #36, #37, #38).
Xac minh thu tu commit DB truoc khi unlock Redis va schema validation.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

# Set test environment variables
os.environ.setdefault("PROJECT_NAME", "Cinema Booking Test")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "30")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_DB", "0")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("TMN_CODE", "SANDBOX_TMN")
os.environ.setdefault("HASH_SECRET", "SANDBOX_HASH_SECRET_KEY")
os.environ.setdefault("VNPAY_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:5173"]')

from contextlib import nullcontext
from app.services.payment_service import PaymentService
from app.services.booking_service import BookingService
from app.models.booking import Booking
from app.models.booking_detail import BookingDetail
from app.utils.enum import BookingStatus, PaymentStatus


def test_payment_confirm_commits_db_before_redis_unlock():
    """Issue #36: confirm_vnpay_payment phai db.commit() truoc khi unlock Redis."""
    db_mock = MagicMock()
    
    mock_booking = MagicMock(spec=Booking)
    mock_booking.id = 100
    mock_booking.showtime_id = 1
    mock_booking.user_id = 5
    mock_booking.total_amount = 100000.0
    mock_booking.booking_status = BookingStatus.PENDING
    mock_booking.payment_status = PaymentStatus.PENDING

    mock_detail = MagicMock(spec=BookingDetail)
    mock_detail.seat_id = 10

    event_log = []

    def fake_commit():
        event_log.append("db_commit")

    db_mock.commit.side_effect = fake_commit
    db_mock.exec.return_value.all.return_value = [mock_detail]

    with patch("app.services.payment_service.redis_client.lock", return_value=nullcontext()), \
         patch("app.services.payment_service.BookingRepository.get_booking_by_id", return_value=mock_booking), \
         patch("app.services.payment_service.BookingRepository.get_booking_with_details", return_value={"id": 100, "email": None}), \
         patch("app.services.payment_service.SeatRepository.book_seat_optimistic") as mock_book, \
         patch("app.services.payment_service.BookingRepository.update_payment_status") as mock_update_status, \
         patch("app.services.payment_service.SeatLockManager.unlock_seat", side_effect=lambda *args, **kwargs: event_log.append("redis_unlock")) as mock_unlock, \
         patch("app.services.payment_service.PaymentService.validate_vnpay_payment_params", return_value=None):

        result = PaymentService.confirm_vnpay_payment(
            db=db_mock,
            booking_id=100,
            vnp_response_code="00",
            vnp_params={"vnp_ResponseCode": "00", "vnp_TransactionStatus": "00"}
        )

        assert result["status"] == "success"
        assert event_log == ["db_commit", "redis_unlock"], f"Actual execution order: {event_log}"


def test_booking_cancel_commits_db_before_redis_unlock():
    """Issue #37: update_payment_status (cancel) phai db.commit() truoc khi unlock Redis."""
    db_mock = MagicMock()

    mock_booking = MagicMock(spec=Booking)
    mock_booking.id = 200
    mock_booking.showtime_id = 2
    mock_booking.user_id = 7
    mock_booking.payment_status = PaymentStatus.PENDING
    mock_booking.booking_status = BookingStatus.PENDING

    event_log = []

    def fake_commit():
        event_log.append("db_commit")

    db_mock.commit.side_effect = fake_commit

    booking_detail_data = {
        "id": 200,
        "bookingId": 200,
        "userId": 7,
        "showtimeId": 2,
        "bookingDate": "2026-08-24T00:00:00",
        "totalAmount": 100000.0,
        "paymentMethod": "VNPAY",
        "paymentStatus": "CANCELLED",
        "bookingStatus": "CANCELLED",
        "seats": [{"seat_id": 15}]
    }

    with patch("app.services.booking_service.BookingRepository.get_booking_by_id", return_value=mock_booking), \
         patch("app.services.booking_service.BookingRepository.update_payment_status"), \
         patch("app.services.booking_service.BookingRepository.get_booking_with_details", return_value=booking_detail_data), \
         patch("app.services.booking_service.SeatRepository.release_seat_optimistic") as mock_release, \
         patch("app.services.booking_service.SeatLockManager.unlock_seat", side_effect=lambda *args, **kwargs: event_log.append("redis_unlock")):

        result = BookingService.update_payment_status(
            db=db_mock,
            booking_id=200,
            payment_status="CANCELLED"
        )

        assert result.paymentStatus == "CANCELLED"
        assert event_log == ["db_commit", "redis_unlock"], f"Actual execution order: {event_log}"


def test_booking_router_uses_literal_validation():
    """Issue #38: Router endpoint phai co Literal validation cho payment_status."""
    source = (BACKEND_ROOT / "app" / "router" / "booking.py").read_text(encoding="utf-8")
    assert 'Literal["FAILED", "CANCELLED"]' in source
