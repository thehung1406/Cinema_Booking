from fastapi import APIRouter, Depends, status
from sqlmodel import Session
from typing import List

from app.core.database import get_session
from app.models.user import User
from app.schemas.booking import (
    BookingCreateRequest,
    BookingResponse,
    BookingDetailResponse
)
from app.services.booking_service import BookingService
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    booking_request: BookingCreateRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    return BookingService.create_booking(
        db=db,
        booking_request=booking_request,
        current_user_id=current_user.id
    )


@router.get("/{booking_id}", response_model=BookingDetailResponse)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    return BookingService.get_booking_by_id(
        db=db,
        booking_id=booking_id,
        user_id=current_user.id
    )


@router.get("", response_model=List[BookingDetailResponse])
def get_user_bookings(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    return BookingService.get_user_bookings(
        db=db,
        user_id=current_user.id
    )


@router.patch("/{booking_id}/payment-status", response_model=BookingDetailResponse)
def update_payment_status(
    booking_id: int,
    payment_status: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    return BookingService.update_payment_status(
        db=db,
        booking_id=booking_id,
        payment_status=payment_status,
        user_id=current_user.id
    )
