from typing import Optional
from sqlmodel import Session, select
from fastapi import HTTPException, status
import logging

from app.core.config import settings
from app.core.redis import redis_client
from app.repositories.booking_repo import BookingRepository
from app.repositories.seat_repo import SeatRepository
from app.models.booking_detail import BookingDetail
from app.worker.tasks import send_payment_success_email_task
from app.utils.enum import BookingStatus, PaymentStatus
from app.utils.redis_lock import SeatLockManager

logger = logging.getLogger(__name__)


class PaymentService:
    @staticmethod
    def _queue_payment_success_email(booking_detail: Optional[dict]) -> None:
        if not booking_detail or not booking_detail.get("email"):
            return

        try:
            send_payment_success_email_task.delay(
                to_email=booking_detail.get("email"),
                booking_detail=booking_detail
            )
        except Exception as e:
            logger.warning(f"Failed to queue payment success email: {e}")

    @staticmethod
    def validate_vnpay_payment_params(booking, params: Optional[dict]) -> Optional[str]:
        """Validate signed VNPay payment data against the server-side booking."""
        if not params:
            return "Thiếu dữ liệu phản hồi VNPay"

        booking_ref = params.get("vnp_TxnRef")
        if str(booking.id) != str(booking_ref):
            return "Mã booking trong phản hồi VNPay không khớp"

        tmn_code = params.get("vnp_TmnCode")
        if tmn_code != settings.TMN_CODE:
            return "Mã merchant VNPay không hợp lệ"

        amount = params.get("vnp_Amount")
        try:
            actual_amount = int(str(amount))
            expected_amount = int(round(float(booking.total_amount) * 100))
        except (TypeError, ValueError):
            return "Số tiền VNPay không hợp lệ"

        if actual_amount != expected_amount:
            return "Số tiền thanh toán không khớp với booking"

        return None

    @staticmethod
    def confirm_vnpay_payment(
        db: Session,
        booking_id: int,
        vnp_response_code: str,
        vnp_params: Optional[dict] = None
    ) -> dict:
        lock_key = f"payment_confirm:{booking_id}"
        email_booking_detail = None
        try:
            with redis_client.lock(lock_key, timeout=60, blocking_timeout=10):
                # Lấy thông tin booking (reload state mới nhất bên trong lock)
                booking = BookingRepository.get_booking_by_id(db=db, booking_id=booking_id)
                
                if not booking:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Booking không tồn tại"
                    )
                
                # Kiểm tra booking đã bị hủy hoặc hết hạn chưa
                if booking.booking_status in (BookingStatus.CANCELLED, BookingStatus.EXPIRED):
                    logger.warning(f"Booking {booking_id} đã bị hủy hoặc hết hạn")
                    return {
                        "status": "failed",
                        "booking": None,
                        "message": "Đơn hàng đã hết hạn hoặc bị hủy"
                    }

                if booking.payment_status == PaymentStatus.FAILED:
                    logger.warning(f"Booking {booking_id} đã ở trạng thái thanh toán thất bại")
                    return {
                        "status": "failed",
                        "booking": None,
                        "message": "Đơn hàng không còn ở trạng thái chờ thanh toán"
                    }

                validation_error = PaymentService.validate_vnpay_payment_params(booking, vnp_params)
                if validation_error:
                    logger.warning(f"VNPay validation failed for booking {booking_id}: {validation_error}")
                    return {
                        "status": "failed",
                        "booking": None,
                        "message": validation_error
                    }

                # Kiểm tra booking đã được thanh toán chưa (idempotent)
                if booking.payment_status == PaymentStatus.PAID:
                    logger.warning(f"Booking {booking_id} đã được thanh toán trước đó")
                    booking_detail = BookingRepository.get_booking_with_details(db=db, booking_id=booking_id)
                    return {
                        "status": "success",
                        "booking": booking_detail,
                        "message": "Booking đã được thanh toán trước đó"
                    }

                effective_response_code = vnp_params.get("vnp_ResponseCode", vnp_response_code) if vnp_params else vnp_response_code
                vnp_transaction_status = vnp_params.get("vnp_TransactionStatus", effective_response_code) if vnp_params else effective_response_code

                # Xử lý theo response code từ VNPay
                if effective_response_code == "00" and vnp_transaction_status == "00":
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
                        payment_status=PaymentStatus.PAID.value
                    )
                    
                    # Commit DB trước khi xóa Redis lock
                    db.commit()
                    logger.info(f"Updated booking {booking_id} payment status to PAID")

                    # Xóa lock khỏi Redis SAU KHI commit DB thành công
                    for seat_id in seat_ids:
                        try:
                            SeatLockManager.unlock_seat(booking.showtime_id, seat_id, booking.user_id)
                        except Exception as e:
                            logger.warning(f"Failed to remove Redis lock for seat {seat_id}: {e}")
                    
                    # Lấy thông tin chi tiết booking
                    booking_detail = BookingRepository.get_booking_with_details(db=db, booking_id=booking_id)
                    email_booking_detail = booking_detail

                    return {
                        "status": "success",
                        "booking": booking_detail,
                        "message": "Thanh toán thành công"
                    }
                else:
                    # Thanh toán thất bại
                    logger.warning(
                        f"VNPay payment failed for booking {booking_id}, "
                        f"response_code: {effective_response_code}, "
                        f"transaction_status: {vnp_transaction_status}"
                    )
                    
                    # Cập nhật trạng thái thanh toán thành FAILED
                    BookingRepository.update_payment_status(
                        db=db,
                        booking_id=booking_id,
                        payment_status=PaymentStatus.FAILED.value
                    )
                    
                    # Release ghế ngay khi thanh toán thất bại
                    booking_details = db.exec(
                        select(BookingDetail).where(BookingDetail.booking_id == booking_id)
                    ).all()
                    seat_ids = [detail.seat_id for detail in booking_details]
                    for seat_id in seat_ids:
                        try:
                            SeatRepository.release_seat_optimistic(db, booking.showtime_id, seat_id, booking.user_id)
                        except Exception as e:
                            logger.warning(f"Failed to release hold for seat {seat_id}: {e}")

                    # Commit DB trước khi xóa Redis lock
                    db.commit()
                    logger.info(f"Updated booking {booking_id} payment status to FAILED and released seats")

                    # Xóa lock khỏi Redis SAU KHI commit DB thành công
                    for seat_id in seat_ids:
                        try:
                            SeatLockManager.unlock_seat(booking.showtime_id, seat_id, booking.user_id)
                        except Exception as e:
                            logger.warning(f"Failed to remove Redis lock for seat {seat_id}: {e}")
                    
                    return {
                        "status": "failed",
                        "booking": None,
                        "message": f"Thanh toán thất bại với mã lỗi: {effective_response_code}"
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
        finally:
            PaymentService._queue_payment_success_email(email_booking_detail)

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

        lock_key = f"payment_confirm:{booking_id}"
        email_booking_detail = None
        try:
            with redis_client.lock(lock_key, timeout=60, blocking_timeout=10):
                booking = BookingRepository.get_booking_by_id(db=db, booking_id=booking_id)
                if not booking:
                    logger.warning(f"VNPay IPN: Booking {booking_id} not found")
                    return {"RspCode": "01", "Message": "Order Not Found"}

                validation_error = PaymentService.validate_vnpay_payment_params(booking, params)
                if validation_error:
                    logger.warning(f"VNPay IPN validation failed for booking {booking_id}: {validation_error}")
                    if "Số tiền" in validation_error:
                        return {"RspCode": "04", "Message": "Invalid Amount"}
                    return {"RspCode": "99", "Message": validation_error}

                # Kiểm tra đơn đã xác nhận trước đó chưa (idempotency)
                if booking.payment_status == PaymentStatus.PAID:
                    logger.info(f"VNPay IPN: Booking {booking_id} already confirmed")
                    return {"RspCode": "02", "Message": "Order already confirmed"}
                    
                if booking.booking_status in (BookingStatus.CANCELLED, BookingStatus.EXPIRED) or booking.payment_status == PaymentStatus.FAILED:
                    logger.info(f"VNPay IPN: Booking {booking_id} already cancelled or failed")
                    return {"RspCode": "02", "Message": "Order already confirmed"}

                vnp_response_code = params.get("vnp_ResponseCode", "")
                vnp_transaction_status = params.get("vnp_TransactionStatus", vnp_response_code)
                
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
                        payment_status=PaymentStatus.PAID.value
                    )
                    
                    # Commit DB trước khi xóa Redis lock
                    db.commit()
                    logger.info(f"VNPay IPN: Successfully processed payment for booking {booking_id}")
                    
                    # Xóa Redis lock SAU KHI commit DB thành công
                    for seat_id in seat_ids:
                        try:
                            SeatLockManager.unlock_seat(booking.showtime_id, seat_id, booking.user_id)
                        except Exception as e:
                            logger.warning(f"Failed to remove Redis lock for seat {seat_id}: {e}")
                    
                    booking_detail = BookingRepository.get_booking_with_details(db=db, booking_id=booking_id)
                    email_booking_detail = booking_detail
                            
                    return {"RspCode": "00", "Message": "Confirm Success"}
                else:
                    # Thanh toán thất bại
                    BookingRepository.update_payment_status(
                        db=db,
                        booking_id=booking_id,
                        payment_status=PaymentStatus.FAILED.value
                    )
                    
                    booking_details = db.exec(
                        select(BookingDetail).where(BookingDetail.booking_id == booking_id)
                    ).all()
                    seat_ids = [detail.seat_id for detail in booking_details]
                    for seat_id in seat_ids:
                        try:
                            SeatRepository.release_seat_optimistic(db, booking.showtime_id, seat_id, booking.user_id)
                        except Exception as e:
                            logger.warning(f"Failed to release seat {seat_id}: {e}")
                            
                    # Commit DB trước khi xóa Redis lock
                    db.commit()
                    logger.info(f"VNPay IPN: Processed failed payment for booking {booking_id}")

                    # Xóa Redis lock SAU KHI commit DB thành công
                    for seat_id in seat_ids:
                        try:
                            SeatLockManager.unlock_seat(booking.showtime_id, seat_id, booking.user_id)
                        except Exception as e:
                            logger.warning(f"Failed to release seat lock on Redis {seat_id}: {e}")

                    return {"RspCode": "00", "Message": "Confirm Success"}
        except Exception as e:
            db.rollback()
            logger.error(f"VNPay IPN error for booking {booking_id}: {str(e)}")
            return {"RspCode": "99", "Message": "Unknown error"}
        finally:
            PaymentService._queue_payment_success_email(email_booking_detail)

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
