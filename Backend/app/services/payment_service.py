from typing import Optional
from sqlmodel import Session
from fastapi import HTTPException, status
import logging

from app.repositories.booking_repo import BookingRepository
from app.repositories.seat_repo import SeatRepository
from app.models.booking_detail import BookingDetail
from sqlmodel import select
from app.worker.tasks import send_payment_success_email_task

logger = logging.getLogger(__name__)


class PaymentService:
    @staticmethod
    def confirm_vnpay_payment(
        db: Session,
        booking_id: int,
        vnp_response_code: str
    ) -> dict:
        try:
            # Lấy thông tin booking
            booking = BookingRepository.get_booking_by_id(db=db, booking_id=booking_id)
            
            if not booking:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Booking không tồn tại"
                )
            
            # Kiểm tra booking đã được thanh toán chưa
            if booking.payment_status == "PAID":
                logger.warning(f"Booking {booking_id} đã được thanh toán trước đó")
                # Vẫn trả về thông tin booking để frontend hiển thị
                booking_detail = BookingRepository.get_booking_with_details(db=db, booking_id=booking_id)
                return {
                    "status": "success",
                    "booking": booking_detail,
                    "message": "Booking đã được thanh toán trước đó"
                }
            
            # Xử lý theo response code từ VNPay
            if vnp_response_code == "00":
                # Thanh toán thành công
                logger.info(f"VNPay payment success for booking {booking_id}")
                
                # Cập nhật trạng thái thanh toán
                BookingRepository.update_payment_status(
                    db=db,
                    booking_id=booking_id,
                    payment_status="PAID"
                )
                
                # ✅ BÂY GIỜ MỚI cập nhật seat_status thành BOOKED
                # Lấy danh sách seat_id từ booking_details
                booking_details = db.exec(
                    select(BookingDetail).where(BookingDetail.booking_id == booking_id)
                ).all()
                
                seat_ids = [detail.seat_id for detail in booking_details]
                
                # Cập nhật seat_status thành BOOKED
                BookingRepository.update_seat_status_to_booked(
                    db=db,
                    showtime_id=booking.showtime_id,
                    seat_ids=seat_ids
                )
                logger.info(f"Updated {len(seat_ids)} seats to BOOKED for booking {booking_id}")
                
                db.commit()
                logger.info(f"Updated booking {booking_id} payment status to PAID")
                
                # Lấy thông tin chi tiết booking
                booking_detail = BookingRepository.get_booking_with_details(db=db, booking_id=booking_id)

                # Gửi email xác nhận (chạy nền qua Celery)
                if booking_detail and booking_detail.get("email"):
                    send_payment_success_email_task.delay(
                        to_email=booking_detail.get("email"),
                        booking_detail=booking_detail
                    )
                
                return {
                    "status": "success",
                    "booking": booking_detail,
                    "message": "Thanh toán thành công"
                }
            else:
                # Thanh toán thất bại
                logger.warning(f"VNPay payment failed for booking {booking_id}, code: {vnp_response_code}")
                
                # Cập nhật trạng thái thanh toán thành FAILED
                BookingRepository.update_payment_status(
                    db=db,
                    booking_id=booking_id,
                    payment_status="FAILED"
                )  
                db.commit()
                logger.info(f"Updated booking {booking_id} payment status to FAILED")
                
                return {
                    "status": "failed",
                    "booking": None,
                    "message": f"Thanh toán thất bại với mã lỗi: {vnp_response_code}"
                }
                
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error confirming VNPay payment: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi xác nhận thanh toán: {str(e)}"
            )
    
    @staticmethod
    def get_payment_status(db: Session, booking_id: int, user_id: Optional[int] = None) -> dict:
        booking = BookingRepository.get_booking_by_id(db=db, booking_id=booking_id)
        
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking không tồn tại"
            )
        
        # Kiểm tra quyền truy cập nếu có user_id
        if user_id and booking.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xem thông tin này"
            )
        
        return {
            "booking_id": booking.id,
            "payment_status": booking.payment_status,
            "booking_status": booking.booking_status,
            "payment_method": booking.payment_method,
            "total_amount": booking.total_amount,
            "booking_date": booking.booking_date
        }
