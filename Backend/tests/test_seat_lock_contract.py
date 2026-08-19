import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "Backend"


def test_redis_lock_uses_atomic_set_nx():
    """Kiểm tra SeatLockManager.lock_seat sử dụng SET NX nguyên tử."""
    source = (BACKEND_ROOT / "app" / "utils" / "redis_lock.py").read_text(encoding="utf-8")
    
    assert "nx=True" in source
    assert "UNLOCK_LUA_SCRIPT" in source
    assert "EXTEND_LUA_SCRIPT" in source
    assert "redis_client.eval(UNLOCK_LUA_SCRIPT" in source


def test_seat_status_model_has_version():
    """Kiểm tra model SeatStatus có trường version phục vụ Optimistic Locking."""
    source = (BACKEND_ROOT / "app" / "models" / "seat_status.py").read_text(encoding="utf-8")
    
    assert "version: int = Field(default=0)" in source


def test_seat_repo_has_optimistic_methods():
    """Kiểm tra SeatRepository chứa các phương thức optimistic locking."""
    source = (BACKEND_ROOT / "app" / "repositories" / "seat_repo.py").read_text(encoding="utf-8")
    
    assert "def hold_seat_optimistic" in source
    assert "def release_seat_optimistic" in source
    assert "SeatStatus.version == current_version" in source


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
