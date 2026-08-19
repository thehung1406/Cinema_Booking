from celery import Task
from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.worker.celery_config import celery_app
from app.core.database import engine
from app.models.seat_status import SeatStatus
from app.models.booking import Booking
from app.models.booking_detail import BookingDetail
from app.utils.enum import SeatStatusEnum, BookingStatus, PaymentStatus
from app.utils.email_service import send_payment_success_email
import logging

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    _session = None

    @property
    def session(self):
        if self._session is None:
            self._session = Session(engine)
        return self._session

@celery_app.task
def cleanup_expired_bookings():
    """
    Task định kỳ cleanup các booking hết hạn
    
    Chạy mỗi 1 phút để:
    - Hủy booking PENDING quá 10 phút chưa thanh toán
    - Cập nhật payment_status thành FAILED
    """
    with Session(engine) as session:
        try:
            # Tìm booking PENDING quá 10 phút (tính từ booking_date)
            ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
            
            statement = select(Booking).where(
                Booking.booking_status == BookingStatus.PENDING,
                Booking.booking_date <= ten_minutes_ago
            )
            expired_bookings = session.exec(statement).all()
            
            count = 0
            
            for booking in expired_bookings:
                # Cập nhật trạng thái booking
                booking.booking_status = BookingStatus.CANCELLED
                booking.payment_status = PaymentStatus.FAILED
                session.add(booking)
                
                count += 1
                logger.info(f"Expired booking {booking.id}")
            
            session.commit()
            logger.info(f"Cleaned up {count} expired bookings")
            return {"expired_bookings": count}
            
        except Exception as e:
            logger.error(f"Error in cleanup_expired_bookings: {str(e)}")
            session.rollback()
            raise e


@celery_app.task
def send_payment_success_email_task(to_email: str, booking_detail: dict):
    """Task gửi email xác nhận thanh toán."""
    try:
        ok = send_payment_success_email(to_email=to_email, booking_detail=booking_detail)
        return {"sent": ok}
    except Exception as e:  # noqa: BLE001
        logger.error("Error sending email to %s: %s", to_email, e)
        raise e
