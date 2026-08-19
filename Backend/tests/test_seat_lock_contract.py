import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "Backend"


def test_redis_lock_uses_atomic_set_nx():
    """Kiểm tra SeatLockManager.lock_seat sử dụng SET NX nguyên tử."""
    source = (BACKEND_ROOT / "app" / "utils" / "redis_lock.py").read_text(encoding="utf-8")
    
    assert "nx=True" in source
    assert "UNLOCK_LUA_SCRIPT" in source
    assert "RENEW_LUA_SCRIPT" in source
    assert "EXTEND_LUA_SCRIPT" in source
    assert "redis_client.eval(UNLOCK_LUA_SCRIPT" in source
    assert "redis_client.eval(RENEW_LUA_SCRIPT" in source
    assert "redis_client.setex(key, ttl, lock_data)" not in source


def test_seat_status_model_has_version():
    """Kiểm tra model SeatStatus có trường version phục vụ Optimistic Locking."""
    source = (BACKEND_ROOT / "app" / "models" / "seat_status.py").read_text(encoding="utf-8")
    
    assert "version: int = Field(default=0)" in source


def test_seat_repo_has_optimistic_methods():
    """Kiểm tra SeatRepository chứa các phương thức optimistic locking."""
    source = (BACKEND_ROOT / "app" / "repositories" / "seat_repo.py").read_text(encoding="utf-8")
    
    assert "def hold_seat_optimistic" in source
    assert "def release_seat_optimistic" in source
    assert "def book_seat_optimistic" in source
    assert "SeatStatus.version == current_version" in source


def test_booking_requires_current_user_hold_before_creating_booking():
    """Booking chỉ được tạo từ ghế đang HOLD bởi đúng user hiện tại."""
    source = (BACKEND_ROOT / "app" / "services" / "booking_service.py").read_text(encoding="utf-8")

    assert "seat_status.status != SeatStatusEnum.HOLD" in source
    assert "seat_status.hold_by_user_id != current_user_id" in source
    assert "seat_status.hold_expired_at <= now" in source


def test_payment_books_only_owned_valid_holds_and_unlocks_by_owner():
    """Payment success phải chuyển HOLD -> BOOKED bằng optimistic owner guard."""
    payment_source = (BACKEND_ROOT / "app" / "services" / "payment_service.py").read_text(encoding="utf-8")
    repo_source = (BACKEND_ROOT / "app" / "repositories" / "seat_repo.py").read_text(encoding="utf-8")

    assert "SeatRepository.book_seat_optimistic" in payment_source
    assert "update_seat_status_to_booked" not in payment_source
    assert "SeatLockManager.unlock_seat(booking.showtime_id, seat_id, booking.user_id)" in payment_source
    assert "SeatStatus.status == SeatStatusEnum.HOLD" in repo_source
    assert "SeatStatus.hold_by_user_id == user_id" in repo_source
    assert "SeatStatus.hold_expired_at > now" in repo_source


def test_hold_and_booking_validate_seat_belongs_to_showtime_room():
    """Không cho hold/booking seat_id của phòng khác với phòng của suất chiếu."""
    seat_service = (BACKEND_ROOT / "app" / "services" / "seat_service.py").read_text(encoding="utf-8")
    booking_service = (BACKEND_ROOT / "app" / "services" / "booking_service.py").read_text(encoding="utf-8")

    assert "seat.room_id != showtime.room_id" in seat_service
    assert "seat.room_id != showtime.room_id" in booking_service


def test_available_count_includes_db_holds_when_redis_is_empty():
    """Available count phải trừ cả HOLD hợp lệ trong DB backup."""
    source = (BACKEND_ROOT / "app" / "services" / "seat_service.py").read_text(encoding="utf-8")

    assert "valid_db_hold_count" in source
    assert "hold_expired_at > now" in source


def test_seat_selection_calls_hold_endpoint_before_booking():
    """Frontend phải gọi /seats/hold trước khi tạo booking."""
    source = (REPO_ROOT / "Frontend" / "src" / "components" / "SeatSelection.jsx").read_text(encoding="utf-8")

    assert 'api.post("/seats/hold"' in source
    assert 'api.post("/seats/release"' in source


def test_payment_return_verifies_vnpay_secure_hash():
    """VNPay return không được tin response code nếu chưa verify chữ ký."""
    router_source = (BACKEND_ROOT / "app" / "router" / "payment.py").read_text(encoding="utf-8")
    schema_source = (BACKEND_ROOT / "app" / "schemas" / "payment.py").read_text(encoding="utf-8")

    assert "vnp_SecureHash" in schema_source
    assert "verify_vnpay_signature" in router_source
    assert "HTTPException" in router_source


def test_booking_and_hold_reject_duplicate_seat_ids():
    """Không cho cùng seat_id xuất hiện nhiều lần trong request."""
    seat_service = (BACKEND_ROOT / "app" / "services" / "seat_service.py").read_text(encoding="utf-8")
    booking_service = (BACKEND_ROOT / "app" / "services" / "booking_service.py").read_text(encoding="utf-8")

    assert "len(set(seat_ids)) != len(seat_ids)" in seat_service
    assert "len(set(seat_ids)) != len(seat_ids)" in booking_service


def test_datetime_columns_are_timezone_aware():
    """Các cột datetime dùng so sánh với UTC-aware datetime phải timezone-aware."""
    model_source = (BACKEND_ROOT / "app" / "models" / "seat_status.py").read_text(encoding="utf-8")
    migration_source = (BACKEND_ROOT / "alembic" / "versions" / "001_initial_migration.py").read_text(encoding="utf-8")

    assert "DateTime(timezone=True)" in model_source
    assert "sa.DateTime(timezone=True)" in migration_source


def test_seat_type_model_declares_room_name_unique_constraint():
    """Model SeatType phải khai báo unique room/name giống migration."""
    source = (BACKEND_ROOT / "app" / "models" / "seat_type.py").read_text(encoding="utf-8")

    assert "UniqueConstraint" in source
    assert '"room_id", "name"' in source


def test_celery_cleanup_handles_expired_seat_holds():
    """Kiểm tra Celery tasks có bước dọn ghế hold hết hạn."""
    source = (BACKEND_ROOT / "app" / "worker" / "tasks.py").read_text(encoding="utf-8")
    
    assert "hold_expired_at <= now" in source
    assert "released_holds" in source


def test_alembic_migration_004_exists():
    """Kiểm tra migration 004 cho cột version tồn tại."""
    migration_file = BACKEND_ROOT / "alembic" / "versions" / "004_add_version_to_seat_status.py"
    assert migration_file.exists()
    
    content = migration_file.read_text(encoding="utf-8")
    assert "add_column" in content
    assert "version" in content
