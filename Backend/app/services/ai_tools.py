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
    from app.utils.booking_ownership import get_owner as booking_owner
    remote_booking=booking_owner(db)=="service"
    if remote_booking and context.showtime_id:
        from app.services.booking_remote import call
        call("POST","/internal/v1/booking-read/context",json=context.model_dump(mode="json"))
    for key, model in (("film_id", Film), ("theater_id", Theater), ("showtime_id", Showtime)):
        value = getattr(context, key)
        from app.services.catalog_remote import get_film
        from app.utils.cinema_ownership import get_owner as cinema_owner
        if key=="showtime_id" and remote_booking: continue
        if value is not None and key!="film_id" and cinema_owner(db)=="service":
            if key=="showtime_id":
                from app.services.sales_service import configuration
                row=configuration(db,value)
            else:
                from app.services.cinema_remote import object_at
                row=object_at(f"/theaters/{value}")
        else:
            row = get_film(db, value) if key == "film_id" and value is not None else (db.get(model, value) if value is not None else None)
        if value is not None and row is None:
            raise HTTPException(422, f"{key} không tồn tại")
    if context.show_date and context.show_date < datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date():
        raise HTTPException(422, "Vui lòng chọn ngày hôm nay hoặc tương lai")
    if context.showtime_id and not remote_booking:
        from app.utils.cinema_ownership import get_owner as cinema_owner
        if cinema_owner(db)=="service":
            from app.services.sales_service import configuration
            from types import SimpleNamespace
            show=configuration(db,context.showtime_id)
            room=SimpleNamespace(theater_id=show.theater_id)
        else:
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
    from app.utils.booking_ownership import get_owner as booking_owner
    if call.name in {"get_showtimes","get_ticket_prices","get_seat_availability"} and booking_owner(db)=="service":
        from app.services.booking_remote import call as booking_call
        return booking_call("POST","/internal/v1/booking-read/tool",json={"call":call.model_dump(mode="json"),"evening":evening})
    if call.name == "search_films":
        from app.utils.catalog_ownership import get_owner
        from app.services.catalog_remote import film_batch, call as catalog_call, FilmFact
        owner = get_owner(db)
        if owner == "service":
            if c.film_id:
                films = list(film_batch([c.film_id]).values())
            elif call_query := call.query.strip():
                films = [FilmFact.model_validate(f) for f in catalog_call("POST", "/internal/v1/films/search", json={"q": call_query, "limit": 8})]
            else: return []
            return [dict(id=f"film:{f.id}", title=f.title, text=f"{f.title}. Thể loại: {f.genre or 'chưa cập nhật'}. {f.description or 'Chưa có mô tả.'}", url=f"/movie/{f.id}", kind="film") for f in films]
        if owner == "maintenance": raise HTTPException(503, "Catalog đang chuyển dữ liệu")
        stmt = select(Film).where(Film.deleted_at.is_(None))
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
    from app.utils.cinema_ownership import get_owner as cinema_owner
    published=cinema_owner(db)=="service"
    if published:
        from app.models.sales import SalesConfiguration as Config
        show=db.exec(future_showtimes(db).where(Config.showtime_id==c.showtime_id)).first()
    else:
        show = db.exec(future_showtimes(db).where(Showtime.id == c.showtime_id)).first()
    if show is None:
        return []
    url = f"/seat-selection/{show.id}"
    if call.name == "get_ticket_prices":
        if published:
            from app.services.sales_service import seat_rows
            prices=list({kind.id:kind for seat,kind in seat_rows(show) if seat.status=="ACTIVE"}.values())
        else:
            prices = db.exec(select(SeatType).where(SeatType.room_id == show.room_id).order_by(SeatType.id)).all()
        return [dict(id=f"price:{p.id}", title=p.name, text=f"Suất {show.id}, ghế {p.name}: {p.base_price:,.0f} VND.", url=url, kind="live") for p in prices]
    if call.name == "get_seat_availability":
        seats = SeatService.get_seats_by_showtime(db, show.id, None)
        available = sum(s["status"] == "AVAILABLE" for s in seats)
        return [dict(id=f"seats:{show.id}", title="Ghế trống", text=f"Suất {show.id}: {available}/{len(seats)} ghế đang trống. Cần kiểm tra lại khi chọn ghế.", url=url, kind="live")]
    raise HTTPException(422, "Công cụ không được phép")
