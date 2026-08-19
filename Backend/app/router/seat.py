from typing import List
from fastapi import APIRouter, Depends, status
from sqlmodel import Session
from app.core.database import get_session
from app.services.seat_service import SeatService
from app.schemas.seat import (
    HoldSeatRequest, 
    ReleaseSeatRequest, 
    SeatStatusResponse, 
    HoldSeatResponse
)
from app.utils.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/seats", tags=["Seats"])


@router.get("/showtime/{showtime_id}", response_model=List[SeatStatusResponse])
def get_seats_by_showtime(
    showtime_id: int,
    db: Session = Depends(get_session)
):
    return SeatService.get_seats_by_showtime(db=db, showtime_id=showtime_id)


@router.post("/hold", response_model=List[HoldSeatResponse], status_code=status.HTTP_200_OK)
def hold_seats(
    request: HoldSeatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Giữ ghế trong Redis với TTL 10 phút (auto-expire)
    Thời gian lock 10 phút khớp với thời gian cho phép thanh toán booking.
    Redis TTL tự động xóa lock sau 10 phút nếu không thanh toán.
    """
    return SeatService.hold_seats(
        db=db,
        showtime_id=request.showtime_id,
        seat_ids=request.seat_ids,
        user_id=current_user.id,
        hold_minutes=10
    )


@router.post("/release", status_code=status.HTTP_200_OK)
def release_seats(
    request: ReleaseSeatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Hủy giữ ghế
    Xóa lock ghế trong Redis
    """
    return SeatService.release_seats(
        db=db,
        showtime_id=request.showtime_id,
        seat_ids=request.seat_ids,
        user_id=current_user.id
    )


@router.get("/showtime/{showtime_id}/available-count")
def get_available_seats_count(
    showtime_id: int,
    db: Session = Depends(get_session)
):
    """
    Đếm số ghế còn trống cho suất chiếu
    """
    count = SeatService.get_available_seats_count(db=db, showtime_id=showtime_id)
    return {
        "showtime_id": showtime_id,
        "available_seats": count
    }


@router.delete("/showtime/{showtime_id}/cancel-hold")
def cancel_hold_for_user(
    showtime_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Hủy tất cả ghế đang hold của user trong suất chiếu
    """
    count = SeatService.cancel_hold_for_user(db=db, showtime_id=showtime_id, user_id=current_user.id)
    return {
        "showtime_id": showtime_id,
        "cancelled_seats": count,
        "message": f"Đã hủy {count} ghế"
    }

