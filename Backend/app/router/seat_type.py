from typing import List
from fastapi import APIRouter, Depends, status
from sqlmodel import Session
from app.core.database import get_session
from app.services.seat_type_service import SeatTypeService
from app.schemas.seat_type import SeatTypeRead, SeatTypeCreate, SeatTypeUpdatePrice
from app.utils.dependencies import get_current_user, require_staff
from app.models.user import User

router = APIRouter(prefix="/seat-types", tags=["Seat Types"])


@router.get("/room/{room_id}", response_model=List[SeatTypeRead])
def get_seat_types_by_room(
    room_id: int,
    db: Session = Depends(get_session)
):
    """Lấy danh sách loại ghế trong phòng"""
    return SeatTypeService.get_seat_types_by_room(db=db, room_id=room_id)


@router.post("/", response_model=SeatTypeRead, status_code=status.HTTP_201_CREATED)
def create_seat_type(
    request: SeatTypeCreate,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session)
):
    """Tạo loại ghế mới (Staff/Admin only)"""
    return SeatTypeService.create_seat_type(
        db=db,
        room_id=request.room_id,
        name=request.name,
        base_price=request.base_price
    )


@router.put("/{seat_type_id}/price", response_model=SeatTypeRead)
def update_seat_type_price(
    seat_type_id: int,
    request: SeatTypeUpdatePrice,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session)
):
    """Cập nhật giá loại ghế (Staff/Admin only).
    Tất cả ghế cùng loại tự động có giá mới.
    """
    return SeatTypeService.update_seat_type_price(
        db=db,
        seat_type_id=seat_type_id,
        new_price=request.base_price
    )


@router.delete("/{seat_type_id}", status_code=status.HTTP_200_OK)
def delete_seat_type(
    seat_type_id: int,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session)
):
    """Xóa loại ghế (Staff/Admin only).
    Chỉ xóa được khi không còn ghế nào thuộc loại này.
    """
    return SeatTypeService.delete_seat_type(db=db, seat_type_id=seat_type_id)
