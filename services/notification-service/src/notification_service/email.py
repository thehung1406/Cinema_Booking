"""SMTP adapter with bounded calls; tests use a local capture server only."""

from email.message import EmailMessage
import smtplib
import ssl


def build_message(data, settings):
    detail = data.booking_detail
    message = EmailMessage()
    message["Subject"] = f"Xác nhận đặt vé #{detail.bookingId}"
    message["From"], message["To"] = settings.smtp_from, str(data.to_email)
    message["Message-ID"] = f"<cinema-booking-{detail.bookingId}-confirmation-v1@notification.local>"
    seats = ", ".join(item.seat_name for item in detail.seats)
    lines = [
        f"Xin chào {detail.fullName or ''}", "Vé của bạn đã được thanh toán và xác nhận.",
        f"Mã đơn: {detail.bookingId}", f"Phim: {detail.filmTitle or ''}",
        f"Rạp: {detail.theaterName or ''}", f"Phòng: {detail.roomName or ''}",
        f"Suất: {detail.showDate or ''} {detail.startTime or ''}", f"Ghế: {seats}",
        f"Tổng tiền: {detail.totalAmount} VND",
    ]
    for item in detail.foodItems:
        lines.append(f"{item.quantity} x {item.name}: {item.line_total} VND")
    lines.append("Cảm ơn bạn đã sử dụng dịch vụ!")
    message.set_content("\n".join(lines))
    return message


def send(data, settings):
    if not settings.smtp_host:
        raise RuntimeError("SMTP is not configured")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds) as smtp:
        if settings.smtp_tls:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        refused = smtp.send_message(build_message(data, settings))
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
