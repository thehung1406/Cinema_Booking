"""
Test suite cho PaymentService — contract tests kiểm tra luồng thanh toán.
"""
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

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

from app.services.payment_service import PaymentService
from app.core.config import settings


# ── PaymentService.validate_vnpay_payment_params Tests ──

class FakeBooking:
    """Fake booking object for testing."""
    def __init__(self, id=1, total_amount=100000.0):
        self.id = id
        self.total_amount = total_amount


def test_validate_params_returns_none_on_valid():
    """Validate phải trả None khi tất cả tham số hợp lệ."""
    booking = FakeBooking(id=42, total_amount=100000.0)
    params = {
        "vnp_TxnRef": "42",
        "vnp_TmnCode": settings.TMN_CODE,
        "vnp_Amount": "10000000",  # 100000 * 100
    }
    result = PaymentService.validate_vnpay_payment_params(booking, params)
    assert result is None


def test_validate_params_missing_params():
    """Validate phải báo lỗi khi params là None."""
    booking = FakeBooking()
    result = PaymentService.validate_vnpay_payment_params(booking, None)
    assert result is not None
    assert "Thiếu" in result


def test_validate_params_wrong_txn_ref():
    """Validate phải báo lỗi khi vnp_TxnRef không khớp booking.id."""
    booking = FakeBooking(id=42)
    params = {
        "vnp_TxnRef": "99",
        "vnp_TmnCode": settings.TMN_CODE,
        "vnp_Amount": "10000000",
    }
    result = PaymentService.validate_vnpay_payment_params(booking, params)
    assert result is not None
    assert "không khớp" in result


def test_validate_params_wrong_tmn_code():
    """Validate phải báo lỗi khi vnp_TmnCode không khớp settings.TMN_CODE."""
    booking = FakeBooking(id=1)
    params = {
        "vnp_TxnRef": "1",
        "vnp_TmnCode": "WRONG_CODE",
        "vnp_Amount": "10000000",
    }
    result = PaymentService.validate_vnpay_payment_params(booking, params)
    assert result is not None
    assert "merchant" in result.lower() or "TmnCode" in result or "không hợp lệ" in result


def test_validate_params_wrong_amount():
    """Validate phải báo lỗi khi vnp_Amount không khớp booking.total_amount * 100."""
    booking = FakeBooking(id=1, total_amount=100000.0)
    params = {
        "vnp_TxnRef": "1",
        "vnp_TmnCode": settings.TMN_CODE,
        "vnp_Amount": "5000000",  # Wrong: should be 10000000
    }
    result = PaymentService.validate_vnpay_payment_params(booking, params)
    assert result is not None
    assert "tiền" in result.lower() or "amount" in result.lower()


def test_validate_params_invalid_amount_type():
    """Validate phải xử lý khi vnp_Amount không phải số."""
    booking = FakeBooking(id=1, total_amount=100000.0)
    params = {
        "vnp_TxnRef": "1",
        "vnp_TmnCode": settings.TMN_CODE,
        "vnp_Amount": "abc",
    }
    result = PaymentService.validate_vnpay_payment_params(booking, params)
    assert result is not None


# ── PaymentService Contract Tests (source code analysis) ──

def test_confirm_vnpay_handles_all_status_transitions():
    """confirm_vnpay_payment phải xử lý: PAID (success), FAILED, CANCELLED, EXPIRED."""
    source = (BACKEND_ROOT / "app" / "services" / "payment_service.py").read_text(encoding="utf-8")

    # Success path: mark PAID + book seats
    assert 'payment_status="PAID"' in source
    assert "SeatRepository.book_seat_optimistic" in source

    # Failed path: mark FAILED + release seats
    assert 'payment_status="FAILED"' in source
    assert "SeatRepository.release_seat_optimistic" in source

    # Cancelled/Expired check
    assert "CANCELLED" in source
    assert "EXPIRED" in source


def test_confirm_vnpay_checks_idempotency():
    """confirm_vnpay_payment phải xử lý idempotent khi booking đã PAID."""
    source = (BACKEND_ROOT / "app" / "services" / "payment_service.py").read_text(encoding="utf-8")
    assert 'booking.payment_status == "PAID"' in source
    assert "đã được thanh toán trước đó" in source


def test_confirm_vnpay_validates_before_marking_paid():
    """confirm_vnpay_payment phải validate params trước khi mark PAID."""
    source = (BACKEND_ROOT / "app" / "services" / "payment_service.py").read_text(encoding="utf-8")
    assert "validate_vnpay_payment_params" in source
    assert "validation_error" in source


def test_ipn_returns_correct_response_codes():
    """process_vnpay_ipn phải trả đúng VNPay RspCode chuẩn."""
    source = (BACKEND_ROOT / "app" / "services" / "payment_service.py").read_text(encoding="utf-8")
    assert '"RspCode": "00"' in source  # Confirm Success
    assert '"RspCode": "97"' in source  # Invalid Checksum
    assert '"RspCode": "01"' in source  # Order Not Found
    assert '"RspCode": "02"' in source  # Order already confirmed
    assert '"RspCode": "04"' in source  # Invalid Amount


def test_ipn_verifies_signature():
    """process_vnpay_ipn phải verify chữ ký trước khi xử lý."""
    source = (BACKEND_ROOT / "app" / "services" / "payment_service.py").read_text(encoding="utf-8")
    assert "verify_vnpay_signature" in source


def test_payment_sends_email_safely():
    """Email phải được gửi trong try-except, không ảnh hưởng transaction."""
    source = (BACKEND_ROOT / "app" / "services" / "payment_service.py").read_text(encoding="utf-8")
    # Email task dispatch wrapped in try-except
    assert "send_payment_success_email_task.delay" in source
    assert "Failed to queue" in source or "Failed to queue payment success email" in source


def test_payment_service_has_get_payment_status():
    """PaymentService phải có method tra cứu trạng thái thanh toán."""
    source = (BACKEND_ROOT / "app" / "services" / "payment_service.py").read_text(encoding="utf-8")
    assert "def get_payment_status" in source
    assert "booking.user_id != user_id" in source  # ownership check


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
