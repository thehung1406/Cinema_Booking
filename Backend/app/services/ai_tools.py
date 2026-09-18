"""Strict read-only allowlist. Availability reuses the existing Redis + DB service."""
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlmodel import select
from app.models import Film, Theater, Showtime, CinemaRoom, SeatType
from app.schemas.ai import ToolCall
from app.services.review_service import future_showtimes, positive_films
from app.services.seat_service import SeatService


def validate_context(db, context):
    for key, model in (("film_id", Film), ("theater_id", Theater), ("showtime_id", Showtime)):
        value = getattr(context, key)
        if value is not None and db.get(model, value) is None:
            raise HTTPException(422, f"{key} không tồn tại")
    if context.show_date and context.show_date < datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date():
        raise HTTPException(422, "Vui lòng chọn ngày hôm nay hoặc tương lai")
    if context.showtime_id:
        show = db.get(Showtime, context.showtime_id)
        room = db.get(CinemaRoom, show.room_id)
        if (context.film_id and show.film_id != context.film_id) or (context.theater_id and room.theater_id != context.theater_id) or (context.show_date and show.show_date != context.show_date):
            raise HTTPException(422, "Suất chiếu không khớp phim, rạp hoặc ngày đã chọn")


def missing_fields(call):
    required = {
        "search_films": (), "get_showtimes": ("film_id", "theater_id", "show_date"),
        "get_positive_films": ("theater_id", "show_date"),
        "get_ticket_prices": ("showtime_id",), "get_seat_availability": ("showtime_id",),
    }[call.name]
    return [field for field in required if getattr(call.context, field) is None]


def run_tool(db, call: ToolCall, evening=False):
    call = ToolCall.model_validate(call)
    validate_context(db, call.context)
    if missing_fields(call):
        raise HTTPException(422, "Thiếu tham số công cụ")
    c = call.context
    if call.name == "search_films":
        stmt = select(Film)
        if c.film_id:
            stmt = stmt.where(Film.id == c.film_id)
        elif call.query.strip():
            stmt = stmt.where(Film.title.contains(call.query.strip(), autoescape=True))
        else:
            return []
        films = db.exec(stmt.order_by(Film.id).limit(8)).all()
        return [dict(id=f"film:{f.id}", title=f.title, text=f"{f.title}. Thể loại: {f.genre or 'chưa cập nhật'}. {f.description or 'Chưa có mô tả.'}", url=f"/movie/{f.id}", kind="film") for f in films]
    if call.name == "get_positive_films":
        films = positive_films(db, c.theater_id, c.show_date, evening=evening)
        return [dict(id=f"positive:{f['film_id']}", title=f["title"],
            text=f"{f['title']}: {f['summary']['positive_ratio']:.0%} tích cực trên {f['summary']['total']} đánh giá hợp lệ trong {f['summary']['window_days']} ngày; còn suất chiếu phù hợp. Xếp hạng theo cận dưới Wilson.",
            url=f["booking_url"], kind="live") for f in films]
    if call.name == "get_showtimes":
        shows = db.exec(future_showtimes(db, c.film_id, c.theater_id, c.show_date, evening).limit(20)).all()
        return [dict(id=f"showtime:{s.id}", title=f"Suất {s.start_time:%H:%M}",
            text=f"{s.show_date:%d/%m/%Y}, {s.start_time:%H:%M}, định dạng {s.format}, mã suất {s.id}.", url=f"/seat-selection/{s.id}", kind="live") for s in shows]
    show = db.exec(future_showtimes(db).where(Showtime.id == c.showtime_id)).first()
    if show is None:
        return []
    url = f"/seat-selection/{show.id}"
    if call.name == "get_ticket_prices":
        prices = db.exec(select(SeatType).where(SeatType.room_id == show.room_id).order_by(SeatType.id)).all()
        return [dict(id=f"price:{p.id}", title=p.name, text=f"Suất {show.id}, ghế {p.name}: {p.base_price:,.0f} VND.", url=url, kind="live") for p in prices]
    if call.name == "get_seat_availability":
        seats = SeatService.get_seats_by_showtime(db, show.id, None)
        available = sum(s["status"] == "AVAILABLE" for s in seats)
        return [dict(id=f"seats:{show.id}", title="Ghế trống", text=f"Suất {show.id}: {available}/{len(seats)} ghế đang trống. Cần kiểm tra lại khi chọn ghế.", url=url, kind="live")]
    raise HTTPException(422, "Công cụ không được phép")
