from typing import List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select
from sqlalchemy import func
from app.models.seat import Seat
from app.models.seat_type import SeatType
from app.models.seat_status import SeatStatus
from app.models.showtime import Showtime
from app.utils.enum import SeatStatusEnum
import logging

logger = logging.getLogger(__name__)


class SeatRepository:
    
    @staticmethod
    def get_seat_by_id(db: Session, seat_id: int) -> Optional[Seat]:
        """Lấy thông tin ghế theo ID"""
        return db.get(Seat, seat_id)
    
    @staticmethod
    def get_seat_with_type(db: Session, seat_id: int) -> Optional[Tuple[Seat, SeatType]]:
        """Lấy ghế kèm thông tin SeatType (tên loại, giá)"""
        statement = (
            select(Seat, SeatType)
            .join(SeatType, SeatType.id == Seat.seat_type_id)
            .where(Seat.id == seat_id)
        )
        return db.exec(statement).first()
    
    @staticmethod
    def get_seats_by_room(db: Session, room_id: int) -> List[Seat]:
        """Lấy tất cả ghế trong phòng"""
        statement = select(Seat).where(Seat.room_id == room_id).order_by(Seat.seat_name)
        return list(db.exec(statement).all())
    
    @staticmethod
    def get_seats_with_type_by_room(db: Session, room_id: int) -> List[Tuple[Seat, SeatType]]:
        """Lấy tất cả ghế trong phòng kèm SeatType (1 query JOIN)"""
        statement = (
            select(Seat, SeatType)
            .join(SeatType, SeatType.id == Seat.seat_type_id)
            .where(Seat.room_id == room_id)
            .order_by(Seat.seat_name)
        )
        return list(db.exec(statement).all())
    
    @staticmethod
    def get_seats_count_by_room(db: Session, room_id: int) -> int:
        """Đếm số ghế trong phòng bằng COUNT(*) — không load data về Python"""
        statement = select(func.count()).select_from(Seat).where(Seat.room_id == room_id)
        return db.exec(statement).one()
    
    @staticmethod
    def get_seat_status(db: Session, showtime_id: int, seat_id: int) -> Optional[SeatStatus]:
        """Lấy trạng thái ghế cho suất chiếu"""
        statement = select(SeatStatus).where(
            SeatStatus.showtime_id == showtime_id,
            SeatStatus.seat_id == seat_id
        )
        return db.exec(statement).first()
    
    @staticmethod
    def get_seats_status_by_showtime(db: Session, showtime_id: int) -> List[SeatStatus]:
        """Lấy trạng thái tất cả ghế trong suất chiếu"""
        statement = select(SeatStatus).where(SeatStatus.showtime_id == showtime_id)
        return list(db.exec(statement).all())
    
    @staticmethod
    def create_seat_status(
        db: Session,
        showtime_id: int, 
        seat_id: int, 
        user_id: int,
        hold_minutes: int = 3
    ) -> SeatStatus:
        """Tạo mới seat_status khi giữ ghế lần đầu"""
        now = datetime.now(timezone.utc)
        seat_status = SeatStatus(
            showtime_id=showtime_id,
            seat_id=seat_id,
            status=SeatStatusEnum.HOLD,
            hold_by_user_id=user_id,
            hold_expired_at=now + timedelta(minutes=hold_minutes),
            created_at=now,
            updated_at=now
        )
        db.add(seat_status)
        db.flush()
        db.refresh(seat_status)
        return seat_status
    
    @staticmethod
    def update_seat_status_hold(
        db: Session,
        seat_status: SeatStatus,
        user_id: int,
        hold_minutes: int = 3
    ) -> SeatStatus:
        """Cập nhật trạng thái ghế sang HOLD"""
        now = datetime.now(timezone.utc)
        seat_status.status = SeatStatusEnum.HOLD
        seat_status.hold_by_user_id = user_id
        seat_status.hold_expired_at = now + timedelta(minutes=hold_minutes)
        seat_status.updated_at = now
        db.add(seat_status)
        db.flush()
        db.refresh(seat_status)
        return seat_status
    
    @staticmethod
    def hold_seat(
        db: Session,
        showtime_id: int, 
        seat_id: int, 
        user_id: int,
        hold_minutes: int = 3
    ) -> SeatStatus:
        """Giữ ghế trong thời gian nhất định"""
        seat_status = SeatRepository.get_seat_status(db, showtime_id, seat_id)
        
        if not seat_status:
            # Tạo mới nếu chưa có
            return SeatRepository.create_seat_status(db, showtime_id, seat_id, user_id, hold_minutes)
        else:
            # Cập nhật trạng thái
            return SeatRepository.update_seat_status_hold(db, seat_status, user_id, hold_minutes)
    
    @staticmethod
    def release_seat(db: Session, showtime_id: int, seat_id: int) -> bool:
        """Hủy giữ ghế"""
        seat_status = SeatRepository.get_seat_status(db, showtime_id, seat_id)
        
        if seat_status and seat_status.status == SeatStatusEnum.HOLD:
            seat_status.status = SeatStatusEnum.AVAILABLE
            seat_status.hold_by_user_id = None
            seat_status.hold_expired_at = None
            seat_status.updated_at = datetime.now(timezone.utc)
            db.add(seat_status)
            db.flush()
            return True
        return False
    
    @staticmethod
    def book_seat(db: Session, showtime_id: int, seat_id: int) -> SeatStatus:
        """Đặt ghế (chuyển từ HOLD sang BOOKED)"""
        seat_status = SeatRepository.get_seat_status(db, showtime_id, seat_id)
        
        if not seat_status:
            raise ValueError(f"Seat status not found for seat {seat_id} in showtime {showtime_id}")
        
        seat_status.status = SeatStatusEnum.BOOKED
        seat_status.hold_expired_at = None
        seat_status.updated_at = datetime.now(timezone.utc)
        db.add(seat_status)
        db.flush()
        db.refresh(seat_status)
        return seat_status
    
    @staticmethod
    def get_booked_seats_count(db: Session, showtime_id: int) -> int:
        """Đếm số ghế đã BOOKED bằng COUNT(*) — hiệu quả hơn load tất cả rồi đếm Python"""
        statement = (
            select(func.count())
            .select_from(SeatStatus)
            .where(
                SeatStatus.showtime_id == showtime_id,
                SeatStatus.status == SeatStatusEnum.BOOKED
            )
        )
        return db.exec(statement).one()
    
    @staticmethod
    def get_available_seats_count(db: Session, showtime_id: int) -> int:
        """Đếm số ghế còn trống bằng COUNT(*).
        Đếm ghế AVAILABLE hoặc chưa có trong seat_status.
        """
        statement = (
            select(func.count())
            .select_from(SeatStatus)
            .where(
                SeatStatus.showtime_id == showtime_id,
                SeatStatus.status == SeatStatusEnum.AVAILABLE
            )
        )
        return db.exec(statement).one()
