"""
Redis Lock Manager for Seat Booking
Quản lý lock ghế tạm thời trong Redis với TTL tự động expire.

Sử dụng các thao tác nguyên tử (SET NX EX, Lua script) để tránh
race condition khi nhiều user cùng lock/unlock ghế đồng thời.
"""
import json
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from app.core.redis import redis_client
import logging

logger = logging.getLogger(__name__)

# ── Lua Scripts (nguyên tử trên Redis) ────────────────────────────────
# Unlock chỉ khi user_id khớp: tránh xóa nhầm lock của người khác
# khi TTL hết giữa bước GET và DELETE.
UNLOCK_LUA_SCRIPT = """
local data = redis.call("GET", KEYS[1])
if data then
    local lock = cjson.decode(data)
    if lock["user_id"] == tonumber(ARGV[1]) then
        return redis.call("DEL", KEYS[1])
    end
    return -1
end
return 0
"""

# Extend TTL chỉ khi user_id khớp: tránh gia hạn nhầm lock người khác.
EXTEND_LUA_SCRIPT = """
local data = redis.call("GET", KEYS[1])
if data then
    local lock = cjson.decode(data)
    if lock["user_id"] == tonumber(ARGV[1]) then
        return redis.call("EXPIRE", KEYS[1], tonumber(ARGV[2]))
    end
    return -1
end
return 0
"""

# Renew lock data + TTL chỉ khi owner hiện tại vẫn khớp.
RENEW_LUA_SCRIPT = """
local data = redis.call("GET", KEYS[1])
if data then
    local lock = cjson.decode(data)
    if lock["user_id"] == tonumber(ARGV[1]) then
        redis.call("SET", KEYS[1], ARGV[2], "EX", tonumber(ARGV[3]))
        return 1
    end
    return -1
end
return 0
"""


class SeatLockManager:
    """
    Quản lý lock ghế trong Redis.
    
    Tất cả thao tác ghi đều sử dụng lệnh nguyên tử:
    - lock_seat: SET key value NX EX ttl (chỉ ghi nếu key chưa tồn tại)
    - unlock_seat: Lua script (check ownership + delete trong 1 lệnh)
    - extend_lock: Lua script (check ownership + expire trong 1 lệnh)
    """
    
    LOCK_PREFIX = "seat_lock"
    DEFAULT_TTL = 600 
    
    @staticmethod
    def _get_lock_key(showtime_id: int, seat_id: int) -> str:
        """Tạo Redis key cho seat lock"""
        return f"{SeatLockManager.LOCK_PREFIX}:{showtime_id}:{seat_id}"
    
    @staticmethod
    def _get_showtime_pattern(showtime_id: int) -> str:
        """Pattern để lấy tất cả locks của 1 suất chiếu"""
        return f"{SeatLockManager.LOCK_PREFIX}:{showtime_id}:*"
    
    @staticmethod
    def _build_lock_data(user_id: int, seat_id: int, showtime_id: int) -> str:
        """Tạo JSON data cho lock entry"""
        return json.dumps({
            "user_id": user_id,
            "locked_at": datetime.utcnow().isoformat(),
            "seat_id": seat_id,
            "showtime_id": showtime_id
        })
    
    @staticmethod
    def lock_seat(
        showtime_id: int, 
        seat_id: int, 
        user_id: int, 
        ttl: int = DEFAULT_TTL
    ) -> bool:
        """
        Lock ghế trong Redis với TTL — sử dụng SET NX EX nguyên tử.
        
        Luồng:
        1. Thử SET NX (chỉ thành công nếu key chưa tồn tại) — nguyên tử
        2. Nếu key đã tồn tại → kiểm tra cùng user không → gia hạn TTL
        3. Nếu user khác đang giữ → trả False
        """
        key = SeatLockManager._get_lock_key(showtime_id, seat_id)
        lock_data = SeatLockManager._build_lock_data(user_id, seat_id, showtime_id)
        
        # Bước 1: Thử lock nguyên tử (SET NX EX)
        # Chỉ thành công nếu key CHƯA tồn tại — không có race condition
        success = redis_client.set(key, lock_data, nx=True, ex=ttl)
        
        if success:
            logger.info(f"Locked seat {seat_id} for user {user_id} with TTL {ttl}s")
            return True
        
        # Bước 2: Key đã tồn tại — kiểm tra có phải cùng user không
        existing_lock = redis_client.get(key)
        if existing_lock:
            try:
                existing_data = json.loads(existing_lock)
                if existing_data.get("user_id") == user_id:
                    result = redis_client.eval(RENEW_LUA_SCRIPT, 1, key, user_id, lock_data, ttl)
                    if result == 1:
                        logger.info(f"Renewed lock for seat {seat_id}, user {user_id}, TTL {ttl}s")
                        return True
                    if result == -1:
                        logger.warning(f"Seat {seat_id} changed owner before renew")
                        return False
                else:
                    logger.warning(
                        f"Seat {seat_id} already locked by user {existing_data.get('user_id')}"
                    )
                    return False
            except json.JSONDecodeError:
                logger.error(f"Invalid lock data in Redis for key {key}")
                return False
        
        # Key biến mất giữa chừng (TTL hết) → thử lock lại
        retry_success = redis_client.set(key, lock_data, nx=True, ex=ttl)
        if retry_success:
            logger.info(f"Locked seat {seat_id} for user {user_id} (retry) with TTL {ttl}s")
            return True
        
        return False
    
    @staticmethod
    def unlock_seat(showtime_id: int, seat_id: int, user_id: Optional[int] = None) -> bool:
        """
        Unlock ghế khỏi Redis — sử dụng Lua script nguyên tử.
        
        Nếu có user_id: chỉ xóa key khi user_id khớp (tránh xóa nhầm lock người khác).
        Nếu không có user_id: xóa key trực tiếp (dùng cho admin/cleanup).
        """
        key = SeatLockManager._get_lock_key(showtime_id, seat_id)
        
        if user_id is not None:
            # Lua script: check ownership + delete trong 1 lệnh nguyên tử
            # Trả về: 1 = xóa OK, 0 = key không tồn tại, -1 = user khác đang giữ
            result = redis_client.eval(UNLOCK_LUA_SCRIPT, 1, key, user_id)
            
            if result == 1:
                logger.info(f"Unlocked seat {seat_id} for showtime {showtime_id}")
                return True
            elif result == -1:
                logger.warning(
                    f"User {user_id} tried to unlock seat {seat_id} owned by another user"
                )
                return False
            else:
                # Key không tồn tại (đã hết TTL hoặc chưa được lock)
                return False
        else:
            # Không cần check ownership — xóa trực tiếp
            deleted = redis_client.delete(key)
            if deleted:
                logger.info(f"Force-unlocked seat {seat_id} for showtime {showtime_id}")
                return True
            return False
    
    @staticmethod
    def is_seat_locked(showtime_id: int, seat_id: int) -> bool:
        """Kiểm tra ghế có đang bị lock không"""
        key = SeatLockManager._get_lock_key(showtime_id, seat_id)
        return redis_client.exists(key) > 0
    
    @staticmethod
    def get_seat_lock_info(showtime_id: int, seat_id: int) -> Optional[Dict]:
        """
        Lấy thông tin lock của ghế
        """
        key = SeatLockManager._get_lock_key(showtime_id, seat_id)
        
        lock_data_str = redis_client.get(key)
        if not lock_data_str:
            return None
        
        try:
            lock_data = json.loads(lock_data_str)
            ttl = redis_client.ttl(key)  # Lấy TTL còn lại
            
            return {
                "user_id": lock_data.get("user_id"),
                "locked_at": lock_data.get("locked_at"),
                "ttl_remaining": ttl,  # Giây còn lại
                "seat_id": seat_id,
                "showtime_id": showtime_id
            }
        except json.JSONDecodeError:
            logger.error(f"Invalid lock data for key {key}")
            return None
    
    @staticmethod
    def get_all_locks_for_showtime(showtime_id: int) -> List[Dict]:
        """
        Lấy tất cả locks của 1 suất chiếu
        Dùng để hiển thị sơ đồ ghế
        """
        pattern = SeatLockManager._get_showtime_pattern(showtime_id)
        keys = redis_client.keys(pattern)
        
        locks = []
        for key in keys:
            # Parse seat_id từ key: seat_lock:showtime_id:seat_id
            try:
                parts = key.split(":")
                seat_id = int(parts[2])
                
                lock_info = SeatLockManager.get_seat_lock_info(showtime_id, seat_id)
                if lock_info:
                    locks.append(lock_info)
            except (IndexError, ValueError) as e:
                logger.error(f"Error parsing key {key}: {e}")
                continue
        
        return locks
    
    @staticmethod
    def unlock_all_seats_for_user(showtime_id: int, user_id: int) -> int:
        """
        Unlock tất cả ghế của 1 user trong suất chiếu
        """
        locks = SeatLockManager.get_all_locks_for_showtime(showtime_id)
        
        count = 0
        for lock in locks:
            if lock.get("user_id") == user_id:
                if SeatLockManager.unlock_seat(showtime_id, lock["seat_id"], user_id):
                    count += 1
        
        logger.info(f"Unlocked {count} seats for user {user_id} in showtime {showtime_id}")
        return count
    
    @staticmethod
    def extend_lock(showtime_id: int, seat_id: int, user_id: int, ttl: int = DEFAULT_TTL) -> bool:
        """
        Gia hạn lock cho ghế (renew TTL) — sử dụng Lua script nguyên tử.
        Chỉ gia hạn nếu user_id khớp với owner hiện tại.
        """
        key = SeatLockManager._get_lock_key(showtime_id, seat_id)
        
        # Lua script: check ownership + expire trong 1 lệnh nguyên tử
        # Trả về: 1 = gia hạn OK, 0 = key không tồn tại, -1 = user khác đang giữ
        result = redis_client.eval(EXTEND_LUA_SCRIPT, 1, key, user_id, ttl)
        
        if result == 1:
            logger.info(f"Extended lock for seat {seat_id} by {ttl}s")
            return True
        elif result == -1:
            logger.warning(f"User {user_id} cannot extend lock owned by another user")
            return False
        else:
            logger.warning(f"Lock for seat {seat_id} not found (TTL expired?)")
            return False


# Singleton instance
seat_lock_manager = SeatLockManager()
