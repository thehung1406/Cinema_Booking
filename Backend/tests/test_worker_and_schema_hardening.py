"""
Test suite cho Issue #40 (VNPayURLRequest hardening) va Issue #41 (Celery DatabaseTask removal).
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

from app.schemas.payment import VNPayURLRequest


def test_vnpay_url_request_schema_hardened():
    """Issue #40: VNPayURLRequest chi nhan bookingId, khong nhan amount/orderInfo/returnUrl de tranh bypass va open redirect."""
    fields = set(VNPayURLRequest.model_fields.keys())
    assert fields == {"bookingId"}


def test_celery_database_task_dead_code_removed():
    """Issue #41: tasks.py khong con chua DatabaseTask singleton anti-pattern."""
    tasks_source = (BACKEND_ROOT / "app" / "worker" / "tasks.py").read_text(encoding="utf-8")
    assert "class DatabaseTask" not in tasks_source
    assert "_session = None" not in tasks_source
    assert "from celery import Task" not in tasks_source
