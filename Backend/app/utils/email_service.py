import logging
import smtplib
from email.message import EmailMessage
from typing import Dict

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_payment_success_email(to_email: str, booking_detail: Dict) -> bool:
    """Gửi email xác nhận thanh toán thành công.

    Trả về True nếu gửi thành công, False nếu thiếu cấu hình SMTP.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP chưa được cấu hình đầy đủ, bỏ qua gửi email")
        return False

    msg = EmailMessage()
    booking_id = booking_detail.get("id") or booking_detail.get("bookingId")
    subject = f"Xac nhan thanh toan dat ve #{booking_id}"
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to_email

    seats = booking_detail.get("seats") or []
    seat_names = ", ".join([(s.get("seat_name") or s.get("seatName") or "") for s in seats])

    body_lines = [
        f"Xin chao {booking_detail.get('fullName') or ''}",
        "Ban da thanh toan thanh cong ve phim.",
        f"Ma don hang: {booking_id}",
        f"Phim: {booking_detail.get('filmTitle') or booking_detail.get('film_title') or ''}",
        f"Rap: {booking_detail.get('theaterName') or booking_detail.get('theater_name') or ''}",
        f"Phong: {booking_detail.get('roomName') or booking_detail.get('room_name') or ''}",
        f"Suat chieu: {(booking_detail.get('showDate') or booking_detail.get('show_date') or '')} {booking_detail.get('startTime') or booking_detail.get('start_time') or ''}",
        f"Ghe: {seat_names}",
        f"Tong tien: {booking_detail.get('totalAmount') or booking_detail.get('total_amount') or ''} VND",
        "Cam on ban da su dung dich vu!",
    ]

    msg.set_content("\n".join(body_lines))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Sent payment success email to %s", to_email)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send email to %s: %s", to_email, exc)
        return False
