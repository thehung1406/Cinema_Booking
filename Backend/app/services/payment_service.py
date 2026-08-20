from typing import Optional
from sqlmodel import Session, select
from fastapi import HTTPException, status
import logging

from app.repositories.booking_repo import BookingRepository
from app.repositories.seat_repo import SeatRepository
from app.models.booking_detail import BookingDetail
from app.worker.tasks import send_payment_success_email_task
from app.utils.redis_lock import SeatLockManager

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
            
            # Kiểm tra booking đã bị hủy hoặc hết hạn chưa
            if booking.booking_status in ("CANCELLED", "EXPIRED"):
                logger.warning(f"Booking {booking_id} đã bị hủy hoặc hết hạn")
                return {
                    "status": "failed",
                    "booking": None,
                    "message": "Đơn hàng đã hết hạn hoặc bị hủy"
                }

            # Kiểm tra booking đã được thanh toán chưa (idempotent)
            if booking.payment_status == "PAID":
                logger.warning(f"Booking {booking_id} đã được thanh toán trước đó")
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

                booking_details = db.exec(
                    select(BookingDetail).where(BookingDetail.booking_id == booking_id)
                ).all()
                
                seat_ids = [detail.seat_id for detail in booking_details]
                
                for seat_id in seat_ids:
                    SeatRepository.book_seat_optimistic(
                        db=db,
                        showtime_id=booking.showtime_id,
                        seat_id=seat_id,
                        user_id=booking.user_id
                    )
                logger.info(f"Updated {len(seat_ids)} seats to BOOKED for booking {booking_id}")

                # Cập nhật trạng thái booking sang PAID và CONFIRMED
                BookingRepository.update_payment_status(
                    db=db,
                    booking_id=booking_id,
                    payment_status="PAID"
                )
                
                # Xóa lock khỏi Redis
                for seat_id in seat_ids:
                    try:
                        SeatLockManager.unlock_seat(booking.showtime_id, seat_id, booking.user_id)
                    except Exception as e:
                        logger.warning(f"Failed to remove Redis lock for seat {seat_id}: {e}")
                
                db.commit()
                logger.info(f"Updated booking {booking_id} payment status to PAID")
                
                # Lấy thông tin chi tiết booking
                booking_detail = BookingRepository.get_booking_with_details(db=db, booking_id=booking_id)

                # Gửi email xác nhận (chạy nền qua Celery, bọc try-except an toàn)
                if booking_detail and booking_detail.get("email"):
                    try:
                        send_payment_success_email_task.delay(
                            to_email=booking_detail.get("email"),
                            booking_detail=booking_detail
                        )
                    except Exception as e:
                        logger.warning(f"Failed to queue payment success email: {e}")
                
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
                
                # Release ghế ngay khi thanh toán thất bại
                booking_details = db.exec(
                    select(BookingDetail).where(BookingDetail.booking_id == booking_id)
                ).all()
                seat_ids = [detail.seat_id for detail in booking_details]
                for seat_id in seat_ids:
                    try:
                        SeatLockManager.unlock_seat(booking.showtime_id, seat_id, booking.user_id)
                        SeatRepository.release_seat_optimistic(db, booking.showtime_id, seat_id, booking.user_id)
                    except Exception as e:
                        logger.warning(f"Failed to release hold for seat {seat_id}: {e}")

                db.commit()
                logger.info(f"Updated booking {booking_id} payment status to FAILED and released seats")
                
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
    def process_vnpay_ipn(db: Session, params: dict) -> dict:
        """
        Xử lý IPN Webhook từ VNPay Server:
        RspCode:
          - "00": Confirm Success
          - "97": Invalid Checksum
          - "01": Order Not Found
          - "02": Order already confirmed
          - "04": Invalid Amount
          - "99": Unknown error
        """
        from app.router.payment import verify_vnpay_signature
        
        if not verify_vnpay_signature(params):
            logger.warning("VNPay IPN signature verification failed")
            return {"RspCode": "97", "Message": "Invalid Checksum"}
        
        booking_ref = params.get("vnp_TxnRef")
        if not booking_ref:
            return {"RspCode": "01", "Message": "Order Not Found"}
            
        try:
            booking_id = int(booking_ref)
        except (ValueError, TypeError):
            return {"RspCode": "01", "Message": "Order Not Found"}
            
        booking = BookingRepository.get_booking_by_id(db=db, booking_id=booking_id)
        if not booking:
            logger.warning(f"VNPay IPN: Booking {booking_id} not found")
            return {"RspCode": "01", "Message": "Order Not Found"}
            
        # Kiểm tra số tiền (vnp_Amount đơn vị xu = VND * 100)
        vnp_amount_str = params.get("vnp_Amount")
        if vnp_amount_str:
            try:
                vnp_amount = int(vnp_amount_str)
                expected_amount = int(round(float(booking.total_amount) * 100))
                if vnp_amount != expected_amount:
                    logger.warning(f"VNPay IPN: Invalid amount {vnp_amount} != expected {expected_amount}")
                    return {"RspCode": "04", "Message": "Invalid Amount"}
            except (ValueError, TypeError):
                return {"RspCode": "04", "Message": "Invalid Amount"}
                
        # Kiểm tra đơn đã xác nhận trước đó chưa (idempotency)
        if booking.payment_status == "PAID":
            logger.info(f"VNPay IPN: Booking {booking_id} already confirmed")
            return {"RspCode": "02", "Message": "Order already confirmed"}
            
        vnp_response_code = params.get("vnp_ResponseCode", "")
        vnp_transaction_status = params.get("vnp_TransactionStatus", vnp_response_code)
        
        try:
            if vnp_response_code == "00" and vnp_transaction_status == "00":
                # Thanh toán thành công
                booking_details = db.exec(
                    select(BookingDetail).where(BookingDetail.booking_id == booking_id)
                ).all()
                seat_ids = [detail.seat_id for detail in booking_details]
                
                for seat_id in seat_ids:
                    SeatRepository.book_seat_optimistic(
                        db=db,
                        showtime_id=booking.showtime_id,
                        seat_id=seat_id,
                        user_id=booking.user_id
                    )
                
                BookingRepository.update_payment_status(
                    db=db,
                    booking_id=booking_id,
                    payment_status="PAID"
                )
                
                for seat_id in seat_ids:
                    try:
                        SeatLockManager.unlock_seat(booking.showtime_id, seat_id, booking.user_id)
                    except Exception as e:
                        logger.warning(f"Failed to remove Redis lock for seat {seat_id}: {e}")
                        
                db.commit()
                logger.info(f"VNPay IPN: Successfully processed payment for booking {booking_id}")
                
                # Gửi email xác nhận
                booking_detail = BookingRepository.get_booking_with_details(db=db, booking_id=booking_id)
                if booking_detail and booking_detail.get("email"):
                    try:
                        send_payment_success_email_task.delay(
                            to_email=booking_detail.get("email"),
                            booking_detail=booking_detail
                        )
                    except Exception as e:
                        logger.warning(f"Failed to queue email task: {e}")
                        
                return {"RspCode": "00", "Message": "Confirm Success"}
            else:
                # Thanh toán thất bại
                BookingRepository.update_payment_status(
                    db=db,
                    booking_id=booking_id,
                    payment_status="FAILED"
                )
                
                booking_details = db.exec(
                    select(BookingDetail).where(BookingDetail.booking_id == booking_id)
                ).all()
                seat_ids = [detail.seat_id for detail in booking_details]
                for seat_id in seat_ids:
                    try:
                        SeatLockManager.unlock_seat(booking.showtime_id, seat_id, booking.user_id)
                        SeatRepository.release_seat_optimistic(db, booking.showtime_id, seat_id, booking.user_id)
                    except Exception as e:
                        logger.warning(f"Failed to release seat {seat_id}: {e}")
                        
                db.commit()
                logger.info(f"VNPay IPN: Processed failed payment for booking {booking_id}")
                return {"RspCode": "00", "Message": "Confirm Success"}
        except Exception as e:
            db.rollback()
            logger.error(f"VNPay IPN error for booking {booking_id}: {str(e)}")
            return {"RspCode": "99", "Message": "Unknown error"}

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
