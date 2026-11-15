"""Fixed Booking and Payment API calls authenticated as the current customer."""

import re
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator


Id = Annotated[int, Field(gt=0, strict=True)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
ORDER_ID = re.compile(r"\b(?:ma\s+don(?:\s+hang)?\s*#?\s*|don(?:\s+hang)?\s*#\s*|don\s+)([1-9]\d{0,17})\b")
PERSONAL_ORDER = re.compile(
    r"\b(?:ve (?:vua mua|da mua|da dat|cua (?:toi|minh))|don (?:hang )?(?:cua (?:toi|minh)|toi|vua dat|gan nhat|moi nhat)|"
    r"(?:da tra tien|da thanh toan).{0,80}(?:chua (?:thay|co|nhan duoc) ve|ve dau)|"
    r"(?:xem|tra cuu|kiem tra) (?:trang thai )?(?:don dat ve|ve cua toi))\b"
)
PAYMENT_COPY = {
    "AWAITING_PAYMENT": "Đơn đang chờ thanh toán hoặc chờ xác nhận thanh toán.",
    "PROCESSING": "Đã ghi nhận thanh toán. Hệ thống đang cấp vé.",
    "REQUIRES_REVIEW": "Giao dịch đang cần đối soát. Bạn có thể liên hệ rạp với mã đơn.",
    "FAILED": "Thanh toán chưa thành công.",
    "ISSUED": "Vé đã được phát hành.",
    "UNKNOWN": "Chưa xác minh được trạng thái thanh toán. Bạn có thể tra lại sau.",
}
SAVED_LOOKUP = "Bạn đã tra đơn ở lượt này. Hãy gửi lại câu hỏi để xem trạng thái mới."


def is_personal_order(text):
    return bool(ORDER_ID.search(text) or PERSONAL_ORDER.search(text))


class SeatSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    showtime_id: Id
    seat_ids: list[Id] = Field(min_length=1, max_length=20)
    reservation_id: UUID | None = None

    @field_validator("seat_ids")
    @classmethod
    def unique_seats(cls, ids):
        if len(ids) != len(set(ids)):
            raise ValueError("Danh sách có ghế trùng")
        return ids


class ReleaseSelection(SeatSelection):
    reservation_id: UUID


class ReleasedSeats(BaseModel):
    released_seats: int = Field(ge=0, strict=True)
    message: str


class HeldSeat(BaseModel):
    seat_id: Id
    seat_name: str
    status: Literal["HOLD"]
    reservation_id: UUID
    hold_expired_at: AwareDatetime


class CheckoutSeat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seat_id: Id
    price: Money


class CheckoutFood(BaseModel):
    model_config = ConfigDict(extra="forbid")
    food_item_id: Id
    quantity: int = Field(strict=True, ge=1, le=20)


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    showtime_id: Id
    reservation_id: UUID
    total_amount: Money = Field(gt=0)
    seats: list[CheckoutSeat] = Field(min_length=1, max_length=20)
    food_items: list[CheckoutFood] = Field(default_factory=list, max_length=50)

    @field_validator("seats", "food_items")
    @classmethod
    def unique_lines(cls, lines):
        ids = [line.seat_id if isinstance(line, CheckoutSeat) else line.food_item_id for line in lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Danh sách có mục trùng")
        return lines


class CheckoutResult(BaseModel):
    bookingId: Id
    expiresAt: AwareDatetime


class CustomerOrder(BaseModel):
    bookingId: Id
    userId: Id
    filmTitle: str | None = None
    theaterName: str | None = None
    showDate: str | None = None
    startTime: str | None = None
    totalAmount: Money
    bookingStatus: str
    seats: list[dict]


class OrderPayment(BaseModel):
    booking_id: Id
    fulfillment_status: Literal["AWAITING_PAYMENT", "PROCESSING", "REQUIRES_REVIEW", "FAILED", "ISSUED"]


class BookingTools:
    def __init__(self, http, settings, user_id, authorization):
        self.http, self.settings = http, settings
        self.user_id, self.authorization = user_id, authorization

    def _request(self, origin, method, path, *, payload=None, key=None, timeout=5):
        headers = {"Authorization": self.authorization}
        if key is not None:
            headers["Idempotency-Key"] = key
        try:
            response = self.http.request(method, origin + path, json=payload, headers=headers, timeout=timeout, follow_redirects=False)
            if response.status_code in {400, 401, 403, 404, 409, 422, 429}:
                try:
                    detail = response.json().get("detail")
                except (ValueError, AttributeError):
                    detail = None
                raise HTTPException(response.status_code, detail if isinstance(detail, str) else "Yêu cầu đặt vé chưa được chấp nhận.")
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "Chưa nhận được kết quả từ dịch vụ đặt vé. Vui lòng thử lại.") from exc

    def hold(self, body):
        result = self._request(self.settings.booking_origin, "POST", "/seats/hold", payload=body.model_dump(mode="json", exclude_none=True))
        try:
            seats = TypeAdapter(list[HeldSeat]).validate_python(result)
            if sorted(seat.seat_id for seat in seats) != sorted(body.seat_ids) or len({(seat.reservation_id, seat.hold_expired_at) for seat in seats}) != 1:
                raise ValueError("Invalid hold result")
            return seats
        except ValueError as exc:
            raise HTTPException(503, "Chưa xác minh được kết quả giữ ghế.") from exc

    def release(self, body):
        result = self._request(self.settings.booking_origin, "POST", "/seats/release", payload=body.model_dump(mode="json"))
        try:
            return ReleasedSeats.model_validate(result)
        except ValueError as exc:
            raise HTTPException(503, "Chưa xác minh được kết quả trả ghế.") from exc

    def checkout(self, body, key):
        if not re.fullmatch(r"[!-~]{1,128}", key):
            raise HTTPException(422, "Idempotency-Key không hợp lệ")
        payload = body.model_dump(mode="json")
        result = self._request(self.settings.booking_origin, "POST", "/bookings", key=key, timeout=12, payload={
            "userId": self.user_id, "showtimeId": body.showtime_id, "reservationId": str(body.reservation_id),
            "totalAmount": payload["total_amount"], "paymentMethod": "Online",
            "seats": payload["seats"], "foodItems": payload["food_items"],
        })
        try:
            if not isinstance(result, dict) or result.get("userId") != self.user_id:
                raise ValueError("Invalid booking owner")
            return CheckoutResult.model_validate(result)
        except ValueError as exc:
            raise HTTPException(503, "Chưa xác minh được kết quả tạo đơn.") from exc

    def get_my_booking(self, text):
        match = ORDER_ID.search(text)
        order_id = int(match[1]) if match else None
        try:
            raw = self._request(self.settings.booking_origin, "GET", f"/bookings/{order_id}" if order_id else "/bookings?limit=1")
            if not order_id:
                if raw == []:
                    return "Bạn chưa có đơn đặt vé trong tài khoản.", "no_results", None
                if not isinstance(raw, list) or len(raw) != 1:
                    raise ValueError("Invalid booking list")
                raw = raw[0]
            order = CustomerOrder.model_validate(raw)
            if order.userId != self.user_id or (order_id and order.bookingId != order_id):
                raise HTTPException(404)
        except (HTTPException, ValueError) as exc:
            if isinstance(exc, HTTPException) and exc.status_code in {403, 404}:
                return "Không tìm thấy đơn trong tài khoản của bạn.", "no_results", None
            return "Chưa thể tra đơn lúc này. Bạn có thể thử lại sau.", "tool_unavailable", None

        stage = "UNKNOWN"
        try:
            payment = OrderPayment.model_validate(self._request(self.settings.payment_origin, "GET", f"/payment/status/{order.bookingId}"))
            if payment.booking_id == order.bookingId:
                stage = payment.fulfillment_status
        except (HTTPException, ValidationError):
            pass  # The booking summary is still usable without payment status.
        booking_state = {"EXPIRED": "Đơn đã hết hạn. ", "CANCELLED": "Đơn đã bị hủy. "}.get(order.bookingStatus, "")
        return booking_state + PAYMENT_COPY[stage], "ok", {
            "booking_id": order.bookingId, "film_title": order.filmTitle, "theater_name": order.theaterName,
            "show_date": order.showDate, "start_time": order.startTime, "seat_count": len(order.seats),
            "total_amount": str(order.totalAmount), "payment_stage": stage,
            "ticket_url": f"/payment-result?bookingId={order.bookingId}" if stage == "ISSUED" else None,
        }
