from typing import List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select
from sqlalchemy import func, update
from fastapi import HTTPException, status
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
    def hold_seat_optimistic(
        db: Session,
        showtime_id: int,
        seat_id: int,
        user_id: int,
        hold_minutes: int = 10
    ) -> SeatStatus:
        """
        Giữ ghế trong DB với Optimistic Lock.
        Chỉ thành công nếu ghế đang AVAILABLE, cùng user, hoặc HOLD đã quá hạn.
        """
        now = datetime.now(timezone.utc)
        expired_at = now + timedelta(minutes=hold_minutes)
        seat_status = SeatRepository.get_seat_status(db, showtime_id, seat_id)

        if not seat_status:
            # Chưa có record trong DB -> INSERT mới
            new_status = SeatStatus(
                showtime_id=showtime_id,
                seat_id=seat_id,
                status=SeatStatusEnum.HOLD,
                hold_by_user_id=user_id,
                hold_expired_at=expired_at,
                version=1,
                created_at=now,
                updated_at=now
            )
            db.add(new_status)
            db.flush()
            db.refresh(new_status)
            return new_status

        # Đã có record -> Kiểm tra trạng thái hiện tại
        if seat_status.status == SeatStatusEnum.BOOKED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ghế đã được đặt"
            )

        # Nếu ghế đang HOLD bởi người khác và chưa hết hạn
        if (
            seat_status.status == SeatStatusEnum.HOLD
            and seat_status.hold_expired_at
            and seat_status.hold_expired_at > now
            and seat_status.hold_by_user_id != user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ghế đang được giữ bởi người khác"
            )

        current_version = seat_status.version

        # Optimistic Lock update: WHERE id = ? AND version = current_version
        result = db.exec(
            update(SeatStatus)
            .where(
                SeatStatus.id == seat_status.id,
                SeatStatus.version == current_version
            )
            .values(
                status=SeatStatusEnum.HOLD,
                hold_by_user_id=user_id,
                hold_expired_at=expired_at,
                version=current_version + 1,
                updated_at=now
            )
        )

        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ghế vừa bị người khác chọn, vui lòng thử lại"
            )

        db.flush()
        db.refresh(seat_status)
        return seat_status

    @staticmethod
    def release_seat_optimistic(db: Session, showtime_id: int, seat_id: int, user_id: int) -> bool:
        """Hủy giữ ghế của user trong DB"""
        seat_status = SeatRepository.get_seat_status(db, showtime_id, seat_id)
        if not seat_status:
            return False

        if seat_status.status == SeatStatusEnum.HOLD and seat_status.hold_by_user_id == user_id:
            now = datetime.now(timezone.utc)
            current_version = seat_status.version
            result = db.exec(
                update(SeatStatus)
                .where(
                    SeatStatus.id == seat_status.id,
                    SeatStatus.version == current_version
                )
                .values(
                    status=SeatStatusEnum.AVAILABLE,
                    hold_by_user_id=None,
                    hold_expired_at=None,
                    version=current_version + 1,
                    updated_at=now
                )
            )
            db.flush()
            return result.rowcount > 0
        return False

    @staticmethod
    def book_seat(db: Session, showtime_id: int, seat_id: int) -> SeatStatus:
        """Đặt ghế (chuyển từ HOLD sang BOOKED)"""
        seat_status = SeatRepository.get_seat_status(db, showtime_id, seat_id)
        now = datetime.now(timezone.utc)
        
        if not seat_status:
            new_status = SeatStatus(
                showtime_id=showtime_id,
                seat_id=seat_id,
                status=SeatStatusEnum.BOOKED,
                version=1,
                created_at=now,
                updated_at=now
            )
            db.add(new_status)
            db.flush()
            db.refresh(new_status)
            return new_status
        
        seat_status.status = SeatStatusEnum.BOOKED
        seat_status.hold_by_user_id = None
        seat_status.hold_expired_at = None
        seat_status.version = seat_status.version + 1
        seat_status.updated_at = now
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
        """Đếm số ghế còn trống bằng COUNT(*)."""
        statement = (
            select(func.count())
            .select_from(SeatStatus)
            .where(
                SeatStatus.showtime_id == showtime_id,
                SeatStatus.status == SeatStatusEnum.AVAILABLE
            )
        )
        return db.exec(statement).one()
