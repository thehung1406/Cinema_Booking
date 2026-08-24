from typing import List
from sqlmodel import Session
from fastapi import HTTPException, status
from datetime import datetime, timezone

from app.models.booking import Booking
from app.repositories.booking_repo import BookingRepository
from app.repositories.seat_repo import SeatRepository
from app.repositories.showtime_repo import ShowtimeRepository
from app.schemas.booking import BookingCreateRequest, BookingResponse, BookingDetailResponse
from app.utils.redis_lock import SeatLockManager
from app.utils.enum import BookingStatus, PaymentStatus, SeatStatusEnum
import logging

logger = logging.getLogger(__name__)


class BookingService:
    """Service xử lý logic nghiệp vụ cho booking"""
    
    @staticmethod
    def create_booking(
        db: Session, 
        booking_request: BookingCreateRequest,
        current_user_id: int
    ) -> BookingResponse:
        try:
            # 1. Validate user
            if booking_request.userId != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Không thể đặt vé cho người dùng khác"
                )
            
            # 2. Kiểm tra showtime
            showtime = ShowtimeRepository.get_showtime_by_id(
                db=db, 
                showtime_id=booking_request.showtimeId
            )
            if not showtime:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Suất chiếu không tồn tại"
                )
            
            # 3. Kiểm tra tất cả ghế
            seat_ids = [seat.seat_id for seat in booking_request.seats]

            if len(set(seat_ids)) != len(seat_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Danh sách ghế bị trùng"
                )

            now = datetime.now(timezone.utc)
            
            for seat_id in seat_ids:
                # Kiểm tra ghế tồn tại
                seat = SeatRepository.get_seat_by_id(db=db, seat_id=seat_id)
                if not seat:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Ghế {seat_id} không tồn tại"
                    )

                if seat.room_id != showtime.room_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Ghế {seat.seat_name} không thuộc phòng của suất chiếu"
                    )
                
                # Booking chỉ hợp lệ khi user đã giữ ghế trước đó.
                seat_status = SeatRepository.get_seat_status(
                    db=db,
                    showtime_id=booking_request.showtimeId,
                    seat_id=seat_id
                )

                if not seat_status or seat_status.status != SeatStatusEnum.HOLD:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Ghế {seat.seat_name} chưa được giữ hoặc không còn khả dụng"
                    )

                if seat_status.hold_by_user_id != current_user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Ghế {seat.seat_name} đang được giữ bởi người dùng khác"
                    )

                if not seat_status.hold_expired_at or seat_status.hold_expired_at <= now:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Thời gian giữ ghế {seat.seat_name} đã hết hạn"
                    )
            
            # 4. Tạo booking
            booking_data = {
                "user_id": booking_request.userId,
                "showtime_id": booking_request.showtimeId,
                "booking_date": datetime.now(timezone.utc),
                "total_amount": booking_request.totalAmount,
                "payment_method": booking_request.paymentMethod,
                "payment_status": PaymentStatus.PENDING.value,
                "booking_status": BookingStatus.PENDING.value
            }
            
            booking = BookingRepository.create_booking(db=db, booking_data=booking_data)
            logger.info(f"Created booking {booking.id} for user {current_user_id}")
            
            # 5. Tạo booking_details
            seats_data = [
                {"seat_id": seat.seat_id, "price": seat.price}
                for seat in booking_request.seats
            ]
            booking_details = BookingRepository.create_booking_details(
                db=db,
                booking_id=booking.id,
                seats=seats_data
            )
            logger.info(f"Created {len(booking_details)} booking details")
            
            # 6. KHÔNG cập nhật seat_status thành BOOKED ngay
            # Chỉ cập nhật khi thanh toán thành công
            # Ghế vẫn giữ trạng thái HOLD trong Redis & DB trong suốt thời gian thanh toán (10 phút)
            
            # 7. Commit transaction
            db.commit()
            logger.info(f"Booking {booking.id} committed successfully")
            
            # Trả về response
            return BookingResponse(
                bookingId=booking.id,
                userId=booking.user_id,
                showtimeId=booking.showtime_id,
                bookingDate=booking.booking_date,
                totalAmount=booking.total_amount,
                paymentMethod=booking.payment_method,
                paymentStatus=booking.payment_status,
                bookingStatus=booking.booking_status,
                seats=seats_data
            )
            
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating booking: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi tạo booking: {str(e)}"
            )
    
    @staticmethod
    def get_booking_by_id(db: Session, booking_id: int, user_id: int) -> BookingDetailResponse:
        """Lấy thông tin chi tiết booking"""
        booking_detail = BookingRepository.get_booking_with_details(db=db, booking_id=booking_id)
        
        if not booking_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking không tồn tại"
            )
        
        # Kiểm tra quyền truy cập
        if booking_detail["userId"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xem booking này"
            )
        
        return BookingDetailResponse(**booking_detail)
    
    @staticmethod
    def get_user_bookings(db: Session, user_id: int, skip: int = 0, limit: int = 50) -> List[BookingDetailResponse]:
        """Lấy tất cả bookings của user.
        Dùng batch JOIN query thay vì loop gọi get_booking_with_details.
        """
        bookings_data = BookingRepository.get_user_bookings_with_details(db=db, user_id=user_id, skip=skip, limit=limit)
        return [BookingDetailResponse(**data) for data in bookings_data]
    
    @staticmethod
    def update_payment_status(
        db: Session, 
        booking_id: int, 
        payment_status: str
    ) -> BookingDetailResponse:
        """Cập nhật trạng thái thanh toán (Staff/Admin only)"""
        # Kiểm tra booking tồn tại
        booking = BookingRepository.get_booking_by_id(db=db, booking_id=booking_id)
        
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking không tồn tại"
            )

        if payment_status not in (PaymentStatus.FAILED, PaymentStatus.CANCELLED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ cho phép cập nhật sang FAILED hoặc CANCELLED"
            )

        if booking.payment_status == PaymentStatus.PAID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể hủy booking đã thanh toán"
            )
        
        try:
            # Cập nhật trạng thái
            BookingRepository.update_payment_status(
                db=db,
                booking_id=booking_id,
                payment_status=payment_status
            )

            booking_detail = BookingRepository.get_booking_with_details(db=db, booking_id=booking_id)
            seats = (booking_detail or {}).get("seats", [])
            for seat in seats:
                seat_id = seat.get("seat_id")
                if seat_id is None:
                    continue
                try:
                    SeatRepository.release_seat_optimistic(db, booking.showtime_id, seat_id, booking.user_id)
                except Exception as e:
                    logger.warning(f"Failed to release hold for seat {seat_id}: {e}")
            
            # Commit DB trước khi xóa Redis lock
            db.commit()

            # Xóa lock khỏi Redis SAU KHI commit DB thành công
            for seat in seats:
                seat_id = seat.get("seat_id")
                if seat_id is None:
                    continue
                try:
                    SeatLockManager.unlock_seat(booking.showtime_id, seat_id, booking.user_id)
                except Exception as e:
                    logger.warning(f"Failed to remove Redis lock for seat {seat_id}: {e}")
            
            # Trả về thông tin chi tiết
            booking_detail = BookingRepository.get_booking_with_details(db=db, booking_id=booking_id)
            return BookingDetailResponse(**booking_detail)
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating payment status for booking {booking_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi cập nhật trạng thái thanh toán: {str(e)}"
            )

