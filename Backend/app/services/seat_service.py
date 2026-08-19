from typing import List, Dict
from datetime import datetime, timedelta, timezone
from sqlmodel import Session
from fastapi import HTTPException, status
from app.repositories.seat_repo import SeatRepository
from app.repositories.showtime_repo import ShowtimeRepository
from app.utils.enum import SeatStatusEnum
from app.utils.redis_lock import SeatLockManager
import logging

logger = logging.getLogger(__name__)


class SeatService:
    
    @staticmethod
    def get_seats_by_showtime(db: Session, showtime_id: int) -> List[Dict]:
        """
        Lấy danh sách ghế và trạng thái theo suất chiếu
        Kết hợp: DB (ghế đã BOOKED) + Redis (ghế đang HOLD)
        Giá lấy từ SeatType.base_price thông qua JOIN
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
        
        # Lấy ghế đã BOOKED từ DB
        booked_seats = SeatRepository.get_seats_status_by_showtime(db=db, showtime_id=showtime_id)
        booked_map = {ss.seat_id: ss for ss in booked_seats if ss.status == SeatStatusEnum.BOOKED}
        
        # Lấy ghế đang HOLD từ Redis
        redis_locks = SeatLockManager.get_all_locks_for_showtime(showtime_id)
        redis_lock_map = {lock["seat_id"]: lock for lock in redis_locks}
        
        result = []
        for seat, seat_type in seat_rows:
            # Priority: BOOKED (DB) > HOLD (Redis) > AVAILABLE
            
            # Kiểm tra ghế đã BOOKED trong DB
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
            
            # Kiểm tra ghế đang HOLD trong Redis
            if seat.id in redis_lock_map:
                lock_info = redis_lock_map[seat.id]
                # Tính thời gian hết hạn
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
            
            # Ghế trống
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
        Giữ nhiều ghế cùng lúc trong Redis
        TTL tự động expire sau 10 phút (khớp với thời gian thanh toán booking)
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
        
        for seat_id in seat_ids:
            # Kiểm tra ghế có tồn tại không
            seat = SeatRepository.get_seat_by_id(db=db, seat_id=seat_id)
            if not seat:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Ghế {seat_id} không tồn tại"
                )
            
            # Kiểm tra ghế đã BOOKED trong DB chưa
            seat_status = SeatRepository.get_seat_status(db=db, showtime_id=showtime_id, seat_id=seat_id)
            if seat_status and seat_status.status == SeatStatusEnum.BOOKED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ghế {seat.seat_name} đã được đặt"
                )
            
            # Kiểm tra ghế có đang bị HOLD trong Redis không
            lock_info = SeatLockManager.get_seat_lock_info(showtime_id, seat_id)
            if lock_info:
                # Nếu người khác đang hold
                if lock_info["user_id"] != user_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Ghế {seat.seat_name} đang được giữ bởi người khác"
                    )
                # Nếu cùng user → gia hạn lock
            
            # Lock ghế trong Redis với TTL
            lock_success = SeatLockManager.lock_seat(
                showtime_id=showtime_id,
                seat_id=seat_id,
                user_id=user_id,
                ttl=ttl_seconds
            )
            
            if not lock_success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Không thể giữ ghế {seat.seat_name}"
                )
            
            # Tính thời gian hết hạn
            hold_expired_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
            
            logger.info(f"User {user_id} locked seat {seat_id} in Redis for {hold_minutes} minutes")
            
            results.append({
                "seat_id": seat_id,
                "seat_name": seat.seat_name,
                "status": SeatStatusEnum.HOLD,
                "hold_expired_at": hold_expired_at
            })
        
        return results
    
    @staticmethod
    def release_seats(
        db: Session,
        showtime_id: int, 
        seat_ids: List[int], 
        user_id: int
    ) -> Dict:
        """
        Hủy giữ ghế khỏi Redis
        User tự hủy hoặc khi chuyển sang trang khác
        """
        released_count = 0
        failed_seats = []
        
        for seat_id in seat_ids:
            # Unlock ghế khỏi Redis
            unlock_success = SeatLockManager.unlock_seat(
                showtime_id=showtime_id,
                seat_id=seat_id,
                user_id=user_id  # Check ownership
            )
            
            if unlock_success:
                released_count += 1
                logger.info(f"User {user_id} released seat {seat_id} from Redis")
            else:
                failed_seats.append(seat_id)
                logger.warning(f"Failed to release seat {seat_id} for user {user_id}")
        
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
        
        # Tổng số ghế trong phòng (dùng COUNT, không load data)
        total_seats = SeatRepository.get_seats_count_by_room(db=db, room_id=showtime.room_id)
        
        # Số ghế đã BOOKED trong DB (dùng COUNT)
        booked_count = SeatRepository.get_booked_seats_count(db=db, showtime_id=showtime_id)
        
        # Số ghế đang HOLD trong Redis
        redis_locks = SeatLockManager.get_all_locks_for_showtime(showtime_id)
        hold_count = len(redis_locks)
        
        available = total_seats - booked_count - hold_count
        return max(0, available)  # Không cho số âm
    
    @staticmethod
    def book_seats_after_payment(
        db: Session,
        showtime_id: int,
        seat_ids: List[int],
        user_id: int,
        booking_id: int
    ) -> bool:
        """
        Chuyển ghế từ HOLD (Redis) sang BOOKED (DB) sau khi thanh toán thành công
        
        Args:
            showtime_id: ID suất chiếu
            seat_ids: Danh sách ID ghế
            user_id: ID user
            booking_id: ID booking vừa tạo
            
        Returns:
            True nếu thành công
        """
        try:
            for seat_id in seat_ids:
                # Kiểm tra ghế có đang bị hold bởi user này không
                lock_info = SeatLockManager.get_seat_lock_info(showtime_id, seat_id)
                
                if not lock_info:
                    logger.error(f"Seat {seat_id} not locked by user {user_id}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Ghế {seat_id} không được giữ bởi bạn"
                    )
                
                if lock_info["user_id"] != user_id:
                    logger.error(f"Seat {seat_id} locked by different user")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Ghế {seat_id} đang được giữ bởi người khác"
                    )
                
                # Lưu vào DB với status BOOKED
                SeatRepository.book_seat(db=db, showtime_id=showtime_id, seat_id=seat_id)
                
                # Xóa lock khỏi Redis
                SeatLockManager.unlock_seat(showtime_id, seat_id, user_id)
                
                logger.info(f"Booked seat {seat_id} and removed Redis lock")
            
            return True
            
        except Exception as e:
            logger.error(f"Error booking seats: {str(e)}")
            # Rollback: Unlock tất cả ghế nếu có lỗi
            for seat_id in seat_ids:
                SeatLockManager.unlock_seat(showtime_id, seat_id, user_id)
            raise
    
    @staticmethod
    def cancel_hold_for_user(db: Session, showtime_id: int, user_id: int) -> int:
        """
        Hủy tất cả ghế đang hold của user trong suất chiếu
        Dùng khi user timeout hoặc hủy booking
        
        Returns:
            Số ghế đã hủy
        """
        count = SeatLockManager.unlock_all_seats_for_user(showtime_id, user_id)
        logger.info(f"Cancelled {count} holds for user {user_id} in showtime {showtime_id}")
        return count
