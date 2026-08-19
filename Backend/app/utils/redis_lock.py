"""
Redis Lock Manager for Seat Booking
Quản lý lock ghế tạm thời trong Redis với TTL tự động expire
"""
import json
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from app.core.redis import redis_client
import logging

logger = logging.getLogger(__name__)


class SeatLockManager:
    """
    Quản lý lock ghế trong Redis
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
    def lock_seat(
        showtime_id: int, 
        seat_id: int, 
        user_id: int, 
        ttl: int = DEFAULT_TTL
    ) -> bool:
        """
        Lock ghế trong Redis với TTL
        """
        key = SeatLockManager._get_lock_key(showtime_id, seat_id)
        
        # Kiểm tra xem ghế đã bị lock chưa
        existing_lock = redis_client.get(key)
        
        if existing_lock:
            try:
                lock_data = json.loads(existing_lock)
                # Nếu đang bị lock bởi user khác
                if lock_data.get("user_id") != user_id:
                    logger.warning(
                        f"Seat {seat_id} already locked by user {lock_data.get('user_id')}"
                    )
                    return False
                # Nếu cùng user → gia hạn lock
            except json.JSONDecodeError:
                logger.error(f"Invalid lock data in Redis for key {key}")
        
        # Lock ghế (hoặc gia hạn nếu cùng user)
        lock_data = {
            "user_id": user_id,
            "locked_at": datetime.utcnow().isoformat(),
            "seat_id": seat_id,
            "showtime_id": showtime_id
        }
        
        redis_client.setex(
            key,
            ttl,
            json.dumps(lock_data)
        )
        
        logger.info(f"Locked seat {seat_id} for user {user_id} with TTL {ttl}s")
        return True
    
    @staticmethod
    def unlock_seat(showtime_id: int, seat_id: int, user_id: Optional[int] = None) -> bool:
        """
        Unlock ghế khỏi Redis
        """
        key = SeatLockManager._get_lock_key(showtime_id, seat_id)
        
        # Nếu cần check ownership
        if user_id is not None:
            existing_lock = redis_client.get(key)
            if existing_lock:
                try:
                    lock_data = json.loads(existing_lock)
                    if lock_data.get("user_id") != user_id:
                        logger.warning(
                            f"User {user_id} tried to unlock seat {seat_id} locked by user {lock_data.get('user_id')}"
                        )
                        return False
                except json.JSONDecodeError:
                    pass
        
        # Xóa key khỏi Redis
        deleted = redis_client.delete(key)
        
        if deleted:
            logger.info(f"Unlocked seat {seat_id} for showtime {showtime_id}")
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
        Gia hạn lock cho ghế (renew TTL)
        """
        key = SeatLockManager._get_lock_key(showtime_id, seat_id)
        
        # Kiểm tra ownership
        existing_lock = redis_client.get(key)
        if not existing_lock:
            return False
        
        try:
            lock_data = json.loads(existing_lock)
            if lock_data.get("user_id") != user_id:
                logger.warning(f"User {user_id} cannot extend lock owned by {lock_data.get('user_id')}")
                return False
            
            # Gia hạn TTL
            redis_client.expire(key, ttl)
            logger.info(f"Extended lock for seat {seat_id} by {ttl}s")
            return True
            
        except json.JSONDecodeError:
            return False


# Singleton instance
seat_lock_manager = SeatLockManager()
