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
from app.utils.enum import SeatStatusEnum
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
            
            for seat_id in seat_ids:
                # Kiểm tra ghế tồn tại
                seat = SeatRepository.get_seat_by_id(db=db, seat_id=seat_id)
                if not seat:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Ghế {seat_id} không tồn tại"
                    )
                
                # Kiểm tra ghế đã được BOOKED chưa (chỉ kiểm tra seat_status)
                # Redis đã xử lý HOLD rồi, chỉ cần check BOOKED thật sự
                seat_status = SeatRepository.get_seat_status(
                    db=db,
                    showtime_id=booking_request.showtimeId,
                    seat_id=seat_id
                )
                # Chỉ reject nếu ghế đã BOOKED thật sự (đã thanh toán)
                if seat_status and seat_status.status == SeatStatusEnum.BOOKED:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Ghế {seat.seat_name} đã được đặt"
                    )
            
            # 4. Tạo booking
            booking_data = {
                "user_id": booking_request.userId,
                "showtime_id": booking_request.showtimeId,
                "booking_date": datetime.now(timezone.utc),
                "total_amount": booking_request.totalAmount,
                "payment_method": booking_request.paymentMethod,
                "payment_status": "PENDING",
                "booking_status": "PENDING"
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
            # Ghế vẫn giữ trạng thái HOLD hoặc sẽ được lock bởi booking này
            
            # 7. Xóa lock Redis (nếu có)
            for seat_id in seat_ids:
                try:
                    SeatLockManager.unlock_seat(
                        showtime_id=booking_request.showtimeId,
                        seat_id=seat_id,
                        user_id=current_user_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to unlock seat {seat_id}: {e}")
            
            # 8. Commit transaction
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
    def get_user_bookings(db: Session, user_id: int) -> List[BookingDetailResponse]:
        """Lấy tất cả bookings của user.
        Dùng batch JOIN query thay vì loop gọi get_booking_with_details.
        """
        bookings_data = BookingRepository.get_user_bookings_with_details(db=db, user_id=user_id)
        return [BookingDetailResponse(**data) for data in bookings_data]
    
    @staticmethod
    def update_payment_status(
        db: Session, 
        booking_id: int, 
        payment_status: str,
        user_id: int
    ) -> BookingDetailResponse:
        """Cập nhật trạng thái thanh toán"""
        # Kiểm tra booking tồn tại và thuộc về user
        booking = BookingRepository.get_booking_by_id(db=db, booking_id=booking_id)
        
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking không tồn tại"
            )
        
        if booking.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền cập nhật booking này"
            )
        
        # Cập nhật trạng thái
        updated_booking = BookingRepository.update_payment_status(
            db=db,
            booking_id=booking_id,
            payment_status=payment_status
        )
        
        db.commit()
        
        # Trả về thông tin chi tiết
        booking_detail = BookingRepository.get_booking_with_details(db=db, booking_id=booking_id)
        return BookingDetailResponse(**booking_detail)
