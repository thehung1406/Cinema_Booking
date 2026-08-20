from celery import Task
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select
from app.worker.celery_config import celery_app
from app.core.database import engine
from app.models.seat_status import SeatStatus
from app.models.booking import Booking
from app.models.booking_detail import BookingDetail
from app.utils.enum import SeatStatusEnum, BookingStatus, PaymentStatus
from app.utils.email_service import send_payment_success_email
from app.utils.redis_lock import SeatLockManager
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
    Task định kỳ cleanup các booking hết hạn và ghế hold quá hạn
    
    Chạy mỗi 1 phút để:
    - Hủy booking PENDING quá 10 phút chưa thanh toán
    - Cập nhật payment_status thành FAILED
    - Release các ghế HOLD quá hạn (hold_expired_at <= now) về AVAILABLE trong DB & Redis
    """
    with Session(engine) as session:
        try:
            now = datetime.now(timezone.utc)
            ten_minutes_ago = now - timedelta(minutes=10)
            
            # 1. Tìm booking PENDING quá 10 phút (tính từ booking_date)
            statement = select(Booking).where(
                Booking.booking_status == BookingStatus.PENDING,
                Booking.booking_date <= ten_minutes_ago
            )
            expired_bookings = session.exec(statement).all()
            
            count = 0
            for booking in expired_bookings:
                booking.booking_status = BookingStatus.CANCELLED
                booking.payment_status = PaymentStatus.FAILED
                session.add(booking)
                
                # Giải phóng ghế trong Redis nếu có
                details = session.exec(
                    select(BookingDetail).where(BookingDetail.booking_id == booking.id)
                ).all()
                for detail in details:
                    try:
                        SeatLockManager.unlock_seat(booking.showtime_id, detail.seat_id, booking.user_id)
                    except Exception:
                        pass
                
                count += 1
                logger.info(f"Expired booking {booking.id}")
            
            # 2. Release ghế HOLD quá hạn trong DB & Redis
            expired_holds = session.exec(
                select(SeatStatus).where(
                    SeatStatus.status == SeatStatusEnum.HOLD,
                    SeatStatus.hold_expired_at <= now
                )
            ).all()
            
            hold_count = 0
            for seat_status in expired_holds:
                try:
                    SeatLockManager.unlock_seat(
                        showtime_id=seat_status.showtime_id,
                        seat_id=seat_status.seat_id,
                        user_id=seat_status.hold_by_user_id
                    )
                except Exception as ex:
                    logger.warning(f"Failed to unlock Redis lock during cleanup: {ex}")

                seat_status.status = SeatStatusEnum.AVAILABLE
                seat_status.hold_by_user_id = None
                seat_status.hold_expired_at = None
                seat_status.version = seat_status.version + 1
                seat_status.updated_at = now
                session.add(seat_status)
                hold_count += 1
            
            session.commit()
            logger.info(f"Cleaned up {count} expired bookings and released {hold_count} expired seat holds")
            return {"expired_bookings": count, "released_holds": hold_count}
            
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
