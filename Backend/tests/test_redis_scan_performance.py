"""
Test suite kiem tra toi uu Redis SCAN + Pipeline cho get_all_locks_for_showtime (Issue #39).
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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

from app.utils.redis_lock import SeatLockManager


def test_contract_no_redis_keys_command_used():
    """Issue #39: redis_lock.py khong duoc dung redis_client.keys() vi gay blocking O(N)."""
    source = (BACKEND_ROOT / "app" / "utils" / "redis_lock.py").read_text(encoding="utf-8")
    assert "redis_client.keys(" not in source
    assert "scan_iter" in source
    assert "pipeline" in source


def test_get_all_locks_uses_scan_and_pipeline():
    """get_all_locks_for_showtime phai dung scan_iter va pipeline batching."""
    showtime_id = 10
    keys = [f"seat_lock:{showtime_id}:101", f"seat_lock:{showtime_id}:102"]
    
    lock_data_101 = json.dumps({"user_id": 1, "locked_at": "2026-08-24T00:00:00", "seat_id": 101, "showtime_id": 10})
    lock_data_102 = json.dumps({"user_id": 2, "locked_at": "2026-08-24T00:01:00", "seat_id": 102, "showtime_id": 10})
    
    pipeline_results = [
        lock_data_101, 300,  # get, ttl cho key 101
        lock_data_102, 450   # get, ttl cho key 102
    ]

    mock_pipe = MagicMock()
    mock_pipe.execute.return_value = pipeline_results

    with patch("app.utils.redis_lock.redis_client.scan_iter", return_value=iter(keys)) as mock_scan, \
         patch("app.utils.redis_lock.redis_client.pipeline", return_value=mock_pipe) as mock_pipeline:

        locks = SeatLockManager.get_all_locks_for_showtime(showtime_id)

        mock_scan.assert_called_once_with(match=f"seat_lock:{showtime_id}:*", count=100)
        assert mock_pipe.get.call_count == 2
        assert mock_pipe.ttl.call_count == 2
        mock_pipe.execute.assert_called_once()

        assert len(locks) == 2
        assert locks[0] == {
            "user_id": 1,
            "locked_at": "2026-08-24T00:00:00",
            "ttl_remaining": 300,
            "seat_id": 101,
            "showtime_id": 10
        }
        assert locks[1] == {
            "user_id": 2,
            "locked_at": "2026-08-24T00:01:00",
            "ttl_remaining": 450,
            "seat_id": 102,
            "showtime_id": 10
        }


def test_get_all_locks_handles_empty_keys():
    """get_all_locks_for_showtime phai tra ve [] ngay khi khong co key nao."""
    with patch("app.utils.redis_lock.redis_client.scan_iter", return_value=iter([])) as mock_scan, \
         patch("app.utils.redis_lock.redis_client.pipeline") as mock_pipeline:

        locks = SeatLockManager.get_all_locks_for_showtime(99)

        assert locks == []
        mock_pipeline.assert_not_called()


def test_get_all_locks_handles_expired_or_corrupt_entries():
    """get_all_locks_for_showtime bo qua nhung key da het han hoac data loi trong pipeline."""
    showtime_id = 5
    keys = [
        f"seat_lock:{showtime_id}:1",  # Hop le
        f"seat_lock:{showtime_id}:2",  # Key het han (ttl <= 0 / None)
        f"seat_lock:{showtime_id}:3",  # Data bi None (het han giua chung)
        f"seat_lock:{showtime_id}:4",  # JSON hong
    ]

    valid_data = json.dumps({"user_id": 10, "locked_at": "2026-08-24T00:00:00", "seat_id": 1, "showtime_id": 5})

    pipeline_results = [
        valid_data, 200,      # Key 1: OK
        valid_data, -1,       # Key 2: TTL hết hạn (-1)
        None, 100,            # Key 3: Data None
        "INVALID_JSON", 50    # Key 4: JSON hỏng
    ]

    mock_pipe = MagicMock()
    mock_pipe.execute.return_value = pipeline_results

    with patch("app.utils.redis_lock.redis_client.scan_iter", return_value=iter(keys)), \
         patch("app.utils.redis_lock.redis_client.pipeline", return_value=mock_pipe):

        locks = SeatLockManager.get_all_locks_for_showtime(showtime_id)

        assert len(locks) == 1
        assert locks[0]["seat_id"] == 1
        assert locks[0]["user_id"] == 10
