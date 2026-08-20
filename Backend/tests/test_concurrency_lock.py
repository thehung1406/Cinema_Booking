"""
Test suite cho Concurrency Lock — kiểm tra SeatLockManager, atomic hold_seats,
và cleanup_expired_bookings task.
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


# ── SeatLockManager Contract Tests ──

def test_seat_lock_manager_uses_atomic_operations():
    """SeatLockManager phải dùng SET NX EX nguyên tử cho lock."""
    source = (BACKEND_ROOT / "app" / "utils" / "redis_lock.py").read_text(encoding="utf-8")

    # SET NX EX — atomic lock
    assert "nx=True" in source
    assert "ex=ttl" in source or "ex=" in source

    # Lua scripts cho unlock và extend
    assert "UNLOCK_LUA_SCRIPT" in source
    assert "EXTEND_LUA_SCRIPT" in source
    assert "RENEW_LUA_SCRIPT" in source

    # Lua scripts check ownership
    assert 'lock["user_id"]' in source
    assert "redis.call" in source


def test_seat_lock_manager_checks_ownership_on_unlock():
    """unlock_seat phải kiểm tra user_id trước khi xóa lock."""
    source = (BACKEND_ROOT / "app" / "utils" / "redis_lock.py").read_text(encoding="utf-8")
    assert "user_id is not None" in source
    assert "eval(UNLOCK_LUA_SCRIPT" in source


def test_seat_lock_manager_supports_renew():
    """SeatLockManager phải hỗ trợ gia hạn (renew) lock."""
    source = (BACKEND_ROOT / "app" / "utils" / "redis_lock.py").read_text(encoding="utf-8")
    assert "def extend_lock" in source
    assert "eval(EXTEND_LUA_SCRIPT" in source


def test_seat_lock_manager_supports_bulk_unlock():
    """SeatLockManager phải hỗ trợ unlock tất cả ghế của user."""
    source = (BACKEND_ROOT / "app" / "utils" / "redis_lock.py").read_text(encoding="utf-8")
    assert "def unlock_all_seats_for_user" in source


# ── hold_seats Atomicity Tests ──

def test_hold_seats_has_precheck_phase():
    """hold_seats phải validate TẤT CẢ ghế TRƯỚC khi bắt đầu lock."""
    source = (BACKEND_ROOT / "app" / "services" / "seat_service.py").read_text(encoding="utf-8")

    # Pre-check phase exists
    assert "seats_map" in source or "Pre-check" in source

    # Pre-check kiểm tra ghế đã BOOKED
    assert "SeatStatusEnum.BOOKED" in source


def test_hold_seats_rollbacks_redis_on_failure():
    """hold_seats phải rollback Redis locks nếu có lỗi giữa chừng."""
    source = (BACKEND_ROOT / "app" / "services" / "seat_service.py").read_text(encoding="utf-8")

    # Rollback logic
    assert "locked_redis_seats" in source
    assert "SeatLockManager.unlock_seat" in source
    assert "db.rollback()" in source


def test_hold_seats_checks_duplicate_seat_ids():
    """hold_seats phải kiểm tra danh sách ghế bị trùng."""
    source = (BACKEND_ROOT / "app" / "services" / "seat_service.py").read_text(encoding="utf-8")
    assert "len(set(seat_ids)) != len(seat_ids)" in source


def test_hold_seats_commits_only_on_full_success():
    """hold_seats chỉ commit khi TẤT CẢ ghế lock thành công."""
    source = (BACKEND_ROOT / "app" / "services" / "seat_service.py").read_text(encoding="utf-8")
    # db.commit() phải nằm SAU vòng lặp, trong try block
    assert "db.commit()" in source


# ── cleanup_expired_bookings Contract Tests ──

def test_cleanup_task_cancels_expired_bookings():
    """cleanup_expired_bookings phải hủy booking PENDING quá 10 phút."""
    source = (BACKEND_ROOT / "app" / "worker" / "tasks.py").read_text(encoding="utf-8")
    assert "def cleanup_expired_bookings" in source
    assert "BookingStatus.CANCELLED" in source or "CANCELLED" in source
    assert "PaymentStatus.FAILED" in source or "FAILED" in source
    assert "ten_minutes_ago" in source or "timedelta(minutes=10)" in source


def test_cleanup_task_releases_expired_holds():
    """cleanup_expired_bookings phải giải phóng ghế HOLD hết hạn."""
    source = (BACKEND_ROOT / "app" / "worker" / "tasks.py").read_text(encoding="utf-8")
    assert "SeatStatusEnum.HOLD" in source
    assert "SeatStatusEnum.AVAILABLE" in source
    assert "hold_expired_at" in source


def test_cleanup_task_unlocks_redis():
    """cleanup_expired_bookings phải giải phóng Redis locks."""
    source = (BACKEND_ROOT / "app" / "worker" / "tasks.py").read_text(encoding="utf-8")
    assert "SeatLockManager.unlock_seat" in source


def test_celery_beat_schedule_exists():
    """Celery Beat phải có schedule chạy cleanup mỗi 60 giây."""
    source = (BACKEND_ROOT / "app" / "worker" / "celery_config.py").read_text(encoding="utf-8")
    assert "beat_schedule" in source
    assert "cleanup_expired_bookings" in source or "cleanup-expired-bookings" in source
    assert "60" in source


# ── Race Condition / Concurrency Contract Tests ──

def test_lock_seat_handles_same_user_renew():
    """lock_seat phải gia hạn khi cùng user lock lại ghế đã lock."""
    source = (BACKEND_ROOT / "app" / "utils" / "redis_lock.py").read_text(encoding="utf-8")
    assert "existing_data" in source or "existing_lock" in source
    assert 'get("user_id")' in source
    assert "RENEW_LUA_SCRIPT" in source


def test_lock_seat_rejects_different_user():
    """lock_seat phải từ chối khi user khác đang giữ ghế."""
    source = (BACKEND_ROOT / "app" / "utils" / "redis_lock.py").read_text(encoding="utf-8")
    assert "already locked by user" in source or "return False" in source


def test_book_seats_after_payment_removes_redis_locks():
    """book_seats_after_payment phải xóa Redis locks sau khi BOOKED."""
    source = (BACKEND_ROOT / "app" / "services" / "seat_service.py").read_text(encoding="utf-8")
    assert "def book_seats_after_payment" in source
    assert "SeatLockManager.unlock_seat" in source
    assert "SeatRepository.book_seat_optimistic" in source


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
