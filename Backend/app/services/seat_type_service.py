from typing import List
from decimal import Decimal
from sqlmodel import Session
from fastapi import HTTPException, status
from app.repositories.seat_type_repo import SeatTypeRepository
from app.repositories.cinema_room_repo import CinemaRoomRepository
import logging

logger = logging.getLogger(__name__)


class SeatTypeService:
    """Service xử lý logic nghiệp vụ cho SeatType"""

    @staticmethod
    def get_seat_types_by_room(db: Session, room_id: int) -> List[dict]:
        """Lấy tất cả loại ghế trong phòng"""
        room = CinemaRoomRepository.get_by_id(db=db, room_id=room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Phòng chiếu không tồn tại"
            )
        
        seat_types = SeatTypeRepository.get_by_room(db=db, room_id=room_id)
        return [
            {
                "id": st.id,
                "room_id": st.room_id,
                "name": st.name,
                "base_price": float(st.base_price)
            }
            for st in seat_types
        ]

    @staticmethod
    def create_seat_type(
        db: Session, room_id: int, name: str, base_price: float
    ) -> dict:
        """Tạo loại ghế mới cho phòng"""
        room = CinemaRoomRepository.get_by_id(db=db, room_id=room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Phòng chiếu không tồn tại"
            )
        
        # Kiểm tra trùng tên
        existing = SeatTypeRepository.get_by_room_and_name(db=db, room_id=room_id, name=name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Loại ghế '{name}' đã tồn tại trong phòng này"
            )
        
        seat_type = SeatTypeRepository.create(
            db=db, room_id=room_id, name=name, base_price=Decimal(str(base_price))
        )
        db.commit()
        
        logger.info(f"Created seat type '{name}' for room {room_id}, price={base_price}")
        return {
            "id": seat_type.id,
            "room_id": seat_type.room_id,
            "name": seat_type.name,
            "base_price": float(seat_type.base_price)
        }

    @staticmethod
    def update_seat_type_price(
        db: Session, seat_type_id: int, new_price: float
    ) -> dict:
        """Cập nhật giá loại ghế — tất cả ghế cùng loại tự có giá mới"""
        seat_type = SeatTypeRepository.get_by_id(db=db, seat_type_id=seat_type_id)
        if not seat_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Loại ghế không tồn tại"
            )
        
        old_price = float(seat_type.base_price)
        seat_type = SeatTypeRepository.update_price(
            db=db, seat_type_id=seat_type_id, new_price=Decimal(str(new_price))
        )
        db.commit()
        
        logger.info(
            f"Updated seat type {seat_type_id} ({seat_type.name}) "
            f"price: {old_price} -> {new_price}"
        )
        return {
            "id": seat_type.id,
            "room_id": seat_type.room_id,
            "name": seat_type.name,
            "base_price": float(seat_type.base_price)
        }

    @staticmethod
    def delete_seat_type(db: Session, seat_type_id: int) -> dict:
        """Xóa loại ghế (chỉ khi không còn ghế tham chiếu)"""
        seat_type = SeatTypeRepository.get_by_id(db=db, seat_type_id=seat_type_id)
        if not seat_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Loại ghế không tồn tại"
            )
        
        try:
            SeatTypeRepository.delete(db=db, seat_type_id=seat_type_id)
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể xóa — vẫn còn ghế thuộc loại này"
            )
        
        logger.info(f"Deleted seat type {seat_type_id}")
        return {"message": f"Đã xóa loại ghế '{seat_type.name}'"}
