from typing import List, Dict
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select
from fastapi import HTTPException, status
from app.repositories.seat_repo import SeatRepository
from app.repositories.showtime_repo import ShowtimeRepository
from app.models.seat_status import SeatStatus
from app.utils.enum import SeatStatusEnum
from app.utils.redis_lock import SeatLockManager
import logging

logger = logging.getLogger(__name__)


class SeatService:
    
    @staticmethod
    def get_seats_by_showtime(db: Session, showtime_id: int) -> List[Dict]:
        """
        Lấy danh sách ghế và trạng thái theo suất chiếu
        Kết hợp: DB (ghế BOOKED + HOLD dự phòng) + Redis (ghế đang HOLD)
        Có Lazy Check: nếu DB có record HOLD nhưng đã quá hạn -> coi như AVAILABLE
        """
        # Kiểm tra showtime có tồn tại không
        showtime = ShowtimeRepository.get_showtime_by_id(db=db, showtime_id=showtime_id)
        
        if not showtime:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Suất chiếu không tồn tại"
            )
        
        # Lấy tất cả ghế trong phòng kèm SeatType (1 query JOIN)
        seat_rows = SeatRepository.get_seats_with_type_by_room(db=db, room_id=showtime.room_id)
        
        if not seat_rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy ghế trong phòng chiếu"
            )
        
        now = datetime.now(timezone.utc)
        
        # Lấy tất cả seat_status từ DB cho suất chiếu này
        all_db_statuses = SeatRepository.get_seats_status_by_showtime(db=db, showtime_id=showtime_id)
        
        booked_map = {ss.seat_id: ss for ss in all_db_statuses if ss.status == SeatStatusEnum.BOOKED}
        # DB HOLD hợp lệ (chưa hết hạn)
        valid_db_hold_map = {
            ss.seat_id: ss for ss in all_db_statuses
            if ss.status == SeatStatusEnum.HOLD and ss.hold_expired_at and ss.hold_expired_at > now
        }
        
        # Lấy ghế đang HOLD từ Redis
        redis_locks = SeatLockManager.get_all_locks_for_showtime(showtime_id)
        redis_lock_map = {lock["seat_id"]: lock for lock in redis_locks}
        
        result = []
        for seat, seat_type in seat_rows:
            # Priority: BOOKED (DB) > HOLD (Redis) > HOLD (DB backup) > AVAILABLE
            
            # 1. Kiểm tra ghế đã BOOKED trong DB
            if seat.id in booked_map:
                result.append({
                    "seat_id": seat.id,
                    "seat_name": seat.seat_name,
                    "seat_type": seat_type.name,
                    "price": float(seat_type.base_price),
                    "status": SeatStatusEnum.BOOKED,
                    "hold_by_user_id": None,
                    "hold_expired_at": None
                })
                continue
            
            # 2. Kiểm tra ghế đang HOLD trong Redis
            if seat.id in redis_lock_map:
                lock_info = redis_lock_map[seat.id]
                locked_at = datetime.fromisoformat(lock_info["locked_at"])
                hold_expired_at = locked_at + timedelta(seconds=lock_info["ttl_remaining"])
                
                result.append({
                    "seat_id": seat.id,
                    "seat_name": seat.seat_name,
                    "seat_type": seat_type.name,
                    "price": float(seat_type.base_price),
                    "status": SeatStatusEnum.HOLD,
                    "hold_by_user_id": lock_info["user_id"],
                    "hold_expired_at": hold_expired_at
                })
                continue
            
            # 3. Kiểm tra ghế đang HOLD trong DB (phòng trường hợp Redis mất key/restart)
            if seat.id in valid_db_hold_map:
                db_hold = valid_db_hold_map[seat.id]
                result.append({
                    "seat_id": seat.id,
                    "seat_name": seat.seat_name,
                    "seat_type": seat_type.name,
                    "price": float(seat_type.base_price),
                    "status": SeatStatusEnum.HOLD,
                    "hold_by_user_id": db_hold.hold_by_user_id,
                    "hold_expired_at": db_hold.hold_expired_at
                })
                continue
            
            # 4. Ghế trống (bao gồm cả ghế HOLD trong DB nhưng đã quá hạn - Lazy Check)
            result.append({
                "seat_id": seat.id,
                "seat_name": seat.seat_name,
                "seat_type": seat_type.name,
                "price": float(seat_type.base_price),
                "status": SeatStatusEnum.AVAILABLE,
                "hold_by_user_id": None,
                "hold_expired_at": None
            })
        
        return result
    
    @staticmethod
    def hold_seats(
        db: Session,
        showtime_id: int, 
        seat_ids: List[int], 
        user_id: int,
        hold_minutes: int = 10
    ) -> List[Dict]:
        """
        Giữ nhiều ghế cùng lúc:
        - Lớp 1: Lock ghế trong Redis với TTL tự động expire
        - Lớp 2: Ghi HOLD vào DB với Optimistic Locking
        """
        # Kiểm tra showtime
        showtime = ShowtimeRepository.get_showtime_by_id(db=db, showtime_id=showtime_id)
        if not showtime:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Suất chiếu không tồn tại"
            )
        
        ttl_seconds = hold_minutes * 60
        results = []
        locked_redis_seats = []
        
        try:
            for seat_id in seat_ids:
                # Kiểm tra ghế có tồn tại không
                seat = SeatRepository.get_seat_by_id(db=db, seat_id=seat_id)
                if not seat:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Ghế {seat_id} không tồn tại"
                    )
                
                # Lớp 1: Lock ghế trong Redis với TTL (nguyên tử)
                lock_success = SeatLockManager.lock_seat(
                    showtime_id=showtime_id,
                    seat_id=seat_id,
                    user_id=user_id,
                    ttl=ttl_seconds
                )
                
                if not lock_success:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Không thể giữ ghế {seat.seat_name} (đang được giữ bởi người khác)"
                    )
                
                locked_redis_seats.append(seat_id)
                
                # Lớp 2: Ghi HOLD vào DB với Optimistic Lock
                SeatRepository.hold_seat_optimistic(
                    db=db,
                    showtime_id=showtime_id,
                    seat_id=seat_id,
                    user_id=user_id,
                    hold_minutes=hold_minutes
                )
                
                hold_expired_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
                logger.info(f"User {user_id} locked seat {seat_id} in Redis & DB for {hold_minutes} minutes")
                
                results.append({
                    "seat_id": seat_id,
                    "seat_name": seat.seat_name,
                    "status": SeatStatusEnum.HOLD,
                    "hold_expired_at": hold_expired_at
                })
            
            db.commit()
            return results
            
        except Exception as e:
            db.rollback()
            # Rollback các ghế đã lock trong Redis trong lượt này
            for seat_id in locked_redis_seats:
                try:
                    SeatLockManager.unlock_seat(showtime_id, seat_id, user_id)
                except Exception as ex:
                    logger.warning(f"Error rolling back Redis lock for seat {seat_id}: {ex}")
            raise e
    
    @staticmethod
    def release_seats(
        db: Session,
        showtime_id: int, 
        seat_ids: List[int], 
        user_id: int
    ) -> Dict:
        """
        Hủy giữ ghế khỏi Redis và DB
        """
        released_count = 0
        failed_seats = []
        
        for seat_id in seat_ids:
            # Unlock ghế khỏi Redis
            redis_unlock = SeatLockManager.unlock_seat(
                showtime_id=showtime_id,
                seat_id=seat_id,
                user_id=user_id
            )
            
            # Unlock ghế trong DB
            db_unlock = SeatRepository.release_seat_optimistic(
                db=db,
                showtime_id=showtime_id,
                seat_id=seat_id,
                user_id=user_id
            )
            
            if redis_unlock or db_unlock:
                released_count += 1
                logger.info(f"User {user_id} released seat {seat_id} from Redis/DB")
            else:
                failed_seats.append(seat_id)
                logger.warning(f"Failed to release seat {seat_id} for user {user_id}")
        
        db.commit()
        return {
            "released_count": released_count,
            "total_requested": len(seat_ids),
            "failed_seats": failed_seats
        }
    
    @staticmethod
    def get_available_seats_count(db: Session, showtime_id: int) -> int:
        """
        Đếm số ghế còn trống
        = Tổng ghế - Ghế BOOKED (DB) - Ghế HOLD (Redis)
        """
        showtime = ShowtimeRepository.get_showtime_by_id(db=db, showtime_id=showtime_id)
        if not showtime:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Suất chiếu không tồn tại"
            )
        
        total_seats = SeatRepository.get_seats_count_by_room(db=db, room_id=showtime.room_id)
        booked_count = SeatRepository.get_booked_seats_count(db=db, showtime_id=showtime_id)
        
        redis_locks = SeatLockManager.get_all_locks_for_showtime(showtime_id)
        hold_count = len(redis_locks)
        
        available = total_seats - booked_count - hold_count
        return max(0, available)
    
    @staticmethod
    def book_seats_after_payment(
        db: Session,
        showtime_id: int,
        seat_ids: List[int],
        user_id: int,
        booking_id: int
    ) -> bool:
        """
        Chuyển ghế từ HOLD (Redis/DB) sang BOOKED (DB) sau khi thanh toán thành công
        """
        try:
            for seat_id in seat_ids:
                # Lưu vào DB với status BOOKED
                SeatRepository.book_seat(db=db, showtime_id=showtime_id, seat_id=seat_id)
                
                # Xóa lock khỏi Redis
                SeatLockManager.unlock_seat(showtime_id, seat_id, user_id)
                
                logger.info(f"Booked seat {seat_id} and removed Redis lock")
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error booking seats: {str(e)}")
            raise
    
    @staticmethod
    def cancel_hold_for_user(db: Session, showtime_id: int, user_id: int) -> int:
        """
        Hủy tất cả ghế đang hold của user trong suất chiếu
        """
        count = SeatLockManager.unlock_all_seats_for_user(showtime_id, user_id)
        
        # Đồng bộ hủy hold trong DB
        now = datetime.now(timezone.utc)
        statement = select(SeatStatus).where(
            SeatStatus.showtime_id == showtime_id,
            SeatStatus.hold_by_user_id == user_id,
            SeatStatus.status == SeatStatusEnum.HOLD
        )
        db_holds = db.exec(statement).all()
        for seat_status in db_holds:
            seat_status.status = SeatStatusEnum.AVAILABLE
            seat_status.hold_by_user_id = None
            seat_status.hold_expired_at = None
            seat_status.version = seat_status.version + 1
            seat_status.updated_at = now
            db.add(seat_status)
        
        db.commit()
        logger.info(f"Cancelled {count} holds for user {user_id} in showtime {showtime_id}")
        return count
