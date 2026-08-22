"""
Test suite cho BookingService — contract tests + unit tests.
Sử dụng mock để test logic nghiệp vụ mà không cần DB/Redis thật.
"""
import ast
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone, timedelta

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

from app.schemas.booking import BookingCreateRequest, BookingResponse, BookingDetailResponse


# ── Contract Tests (source code analysis) ──

def test_booking_service_has_required_methods():
    """BookingService phải có đầy đủ các method nghiệp vụ."""
    source = (BACKEND_ROOT / "app" / "services" / "booking_service.py").read_text(encoding="utf-8")
    assert "def create_booking" in source
    assert "def get_booking_by_id" in source
    assert "def get_user_bookings" in source
    assert "def update_payment_status" in source


def test_create_booking_validates_user_ownership():
    """create_booking phải kiểm tra userId khớp current_user_id."""
    source = (BACKEND_ROOT / "app" / "services" / "booking_service.py").read_text(encoding="utf-8")
    assert "booking_request.userId != current_user_id" in source


def test_create_booking_checks_hold_ownership():
    """create_booking phải kiểm tra hold_by_user_id == current_user_id."""
    source = (BACKEND_ROOT / "app" / "services" / "booking_service.py").read_text(encoding="utf-8")
    assert "seat_status.hold_by_user_id != current_user_id" in source


def test_create_booking_checks_hold_expiry():
    """create_booking phải kiểm tra ghế hold chưa hết hạn."""
    source = (BACKEND_ROOT / "app" / "services" / "booking_service.py").read_text(encoding="utf-8")
    assert "hold_expired_at" in source


def test_create_booking_checks_seat_in_room():
    """create_booking phải kiểm tra ghế thuộc phòng của suất chiếu."""
    source = (BACKEND_ROOT / "app" / "services" / "booking_service.py").read_text(encoding="utf-8")
    assert "seat.room_id != showtime.room_id" in source


def test_create_booking_checks_duplicate_seats():
    """create_booking phải phát hiện ghế trùng lặp."""
    source = (BACKEND_ROOT / "app" / "services" / "booking_service.py").read_text(encoding="utf-8")
    assert "len(set(seat_ids)) != len(seat_ids)" in source


def test_update_payment_status_restricts_values():
    """update_payment_status chỉ cho phép FAILED hoặc CANCELLED."""
    source = (BACKEND_ROOT / "app" / "services" / "booking_service.py").read_text(encoding="utf-8")
    assert '"FAILED"' in source or "PaymentStatus.FAILED" in source
    assert '"CANCELLED"' in source or "PaymentStatus.CANCELLED" in source
    assert ("payment_status ==" in source or "booking.payment_status" in source) and ('"PAID"' in source or "PaymentStatus.PAID" in source)


def test_update_payment_status_admin_only():
    """PATCH /payment-status endpoint phải yêu cầu require_staff."""
    router_source = (BACKEND_ROOT / "app" / "router" / "booking.py").read_text(encoding="utf-8")
    assert "require_staff" in router_source
    assert "Depends(require_staff)" in router_source


def test_booking_schemas_have_required_fields():
    """Booking schemas phải có đầy đủ fields."""
    create_fields = set(BookingCreateRequest.model_fields.keys())
    assert {"userId", "showtimeId", "totalAmount", "paymentMethod", "seats"}.issubset(create_fields)

    response_fields = set(BookingResponse.model_fields.keys())
    assert {"bookingId", "userId", "showtimeId", "totalAmount", "paymentStatus"}.issubset(response_fields)

    detail_fields = set(BookingDetailResponse.model_fields.keys())
    assert {"filmTitle", "theaterName", "roomName", "showDate", "seats"}.issubset(detail_fields)


def test_booking_repository_uses_join_queries():
    """BookingRepository phải dùng JOIN thay vì N+1 queries."""
    source = (BACKEND_ROOT / "app" / "repositories" / "booking_repo.py").read_text(encoding="utf-8")
    assert ".join(" in source
    assert "get_user_bookings_with_details" in source
    assert "booking_id.in_" in source  # batch query for seats


def test_booking_repository_supports_pagination():
    """BookingRepository phải hỗ trợ pagination (skip/limit)."""
    source = (BACKEND_ROOT / "app" / "repositories" / "booking_repo.py").read_text(encoding="utf-8")
    assert "skip" in source
    assert "limit" in source
    assert ".offset(" in source
    assert ".limit(" in source


if __name__ == "__main__":
    # Run all test functions
    import pytest
    pytest.main([__file__, "-v"])
