from typing import List, Optional
from decimal import Decimal
from sqlmodel import Session, select
from app.models.seat_type import SeatType


class SeatTypeRepository:
    """Repository xử lý các thao tác database với SeatType"""

    @staticmethod
    def get_by_id(db: Session, seat_type_id: int) -> Optional[SeatType]:
        """Lấy SeatType theo ID"""
        return db.get(SeatType, seat_type_id)

    @staticmethod
    def get_by_room(db: Session, room_id: int) -> List[SeatType]:
        """Lấy tất cả SeatType trong phòng"""
        statement = select(SeatType).where(SeatType.room_id == room_id).order_by(SeatType.name)
        return list(db.exec(statement).all())

    @staticmethod
    def get_by_room_and_name(db: Session, room_id: int, name: str) -> Optional[SeatType]:
        """Lấy SeatType theo phòng và tên loại"""
        statement = select(SeatType).where(
            SeatType.room_id == room_id,
            SeatType.name == name
        )
        return db.exec(statement).first()

    @staticmethod
    def create(db: Session, room_id: int, name: str, base_price: Decimal) -> SeatType:
        """Tạo SeatType mới"""
        seat_type = SeatType(
            room_id=room_id,
            name=name,
            base_price=base_price
        )
        db.add(seat_type)
        db.flush()
        db.refresh(seat_type)
        return seat_type

    @staticmethod
    def update_price(db: Session, seat_type_id: int, new_price: Decimal) -> Optional[SeatType]:
        """Cập nhật giá của SeatType — tất cả ghế cùng loại tự có giá mới"""
        seat_type = db.get(SeatType, seat_type_id)
        if seat_type:
            seat_type.base_price = new_price
            db.add(seat_type)
            db.flush()
            db.refresh(seat_type)
        return seat_type

    @staticmethod
    def delete(db: Session, seat_type_id: int) -> bool:
        """Xóa SeatType (chỉ khi không còn ghế nào tham chiếu)"""
        seat_type = db.get(SeatType, seat_type_id)
        if not seat_type:
            return False
        db.delete(seat_type)
        db.flush()
        return True
