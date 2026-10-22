"""Transactional administration workflows corresponding to SD01–SD07."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, delete, func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.models import (Booking, BookingDetail, CinemaRoom, Film, FilmFormat, Format,
    Genre, KnowledgeChunk, KnowledgeDocument, Role, Seat, SeatStatus, SeatType, Showtime,
    Theater, User)
from app.models.ai import utcnow
from app.services.rag_service import EMBEDDING_VERSION, upsert_document
from app.utils.security import hash_password


def get(db, model, key, *, lock=False):
    stmt = select(model).where(model.id == key)
    if lock:
        stmt = stmt.with_for_update(of=model)
    item = db.exec(stmt).first()
    if item is None or getattr(item, "deleted_at", None):
        raise HTTPException(404, "Không tìm thấy dữ liệu")
    return item


def save(db, item):
    try:
        db.add(item)
        db.commit()
        db.refresh(item)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Dữ liệu bị trùng hoặc đang được sử dụng. Vui lòng tải lại.")
    return item


def remove(db, item):
    try:
        db.delete(item)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Dữ liệu đang được sử dụng, không thể xóa")
    return {"message": "Đã xóa thành công"}


def film_write(db, body, film_id=None):
    film = get(db, Film, film_id, lock=True) if film_id else Film()
    genres = db.exec(select(Genre).where(Genre.id.in_(set(body.genre_ids)))).all()
    formats = db.exec(select(Format).where(Format.id.in_(set(body.format_ids)))).all()
    if len(genres) != len(set(body.genre_ids)) or len(formats) != len(set(body.format_ids)):
        raise HTTPException(400, "Thể loại hoặc định dạng không tồn tại")
    if film_id:
        shows = db.exec(select(Showtime).where(Showtime.film_id == film_id)).all()
        for show in shows:
            minutes = (datetime.combine(show.show_date, show.end_time) - datetime.combine(show.show_date, show.start_time)).total_seconds()/60
            if show.format_id not in body.format_ids:
                raise HTTPException(409, "Không thể bỏ định dạng đã có lịch chiếu")
            if show.status == "ACTIVE" and (not body.release_date <= show.show_date <= body.end_date or minutes < body.duration_minutes):
                raise HTTPException(409, "Ngày chiếu hoặc thời lượng mới không phù hợp lịch chiếu hiện có")
    for key, value in body.model_dump(exclude={"genre_ids", "format_ids"}).items():
        setattr(film, key, value)
    film.genre_items, film.format_items = list(genres), list(formats)
    return save(db, film)


def film_delete(db, film_id):
    film = get(db, Film, film_id, lock=True)
    if db.exec(select(Showtime.id).where(Showtime.film_id == film_id).limit(1)).first():
        raise HTTPException(409, "Phim đã có lịch chiếu, không thể xóa")
    film.deleted_at = utcnow()
    save(db, film)
    return {"message": "Đã xóa phim"}


def room_write(db, body, room_id=None):
    room = get(db, CinemaRoom, room_id, lock=True) if room_id else CinemaRoom()
    get(db, Theater, body.theater_id)
    duplicate = db.exec(select(CinemaRoom.id).where(CinemaRoom.theater_id == body.theater_id,
        CinemaRoom.name == body.name, CinemaRoom.deleted_at.is_(None), CinemaRoom.id != (room_id or 0))).first()
    if duplicate:
        raise HTTPException(409, "Tên phòng đã tồn tại trong rạp")
    if room_id:
        count = db.exec(select(func.count(Seat.id)).where(Seat.room_id == room_id)).one()
        if body.capacity < count:
            raise HTTPException(409, "Sức chứa không được nhỏ hơn số ghế hiện có")
        if body.theater_id != room.theater_id and db.exec(select(Showtime.id)
                .where(Showtime.room_id == room_id).limit(1)).first():
            raise HTTPException(409, "Phòng đã có lịch chiếu; không thể chuyển rạp")
        now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
        has_upcoming_shows = db.exec(select(Showtime.id).where(Showtime.room_id == room_id,
            Showtime.status == "ACTIVE", or_(Showtime.show_date > now.date(),
                and_(Showtime.show_date == now.date(), Showtime.end_time > now.time().replace(tzinfo=None))))
            .limit(1)).first()
        if has_upcoming_shows and body.status != "ACTIVE":
            raise HTTPException(409, "Phòng đang có lịch chiếu chưa kết thúc; không thể bảo trì")
    for key, value in body.model_dump().items():
        setattr(room, key, value)
    return save(db, room)


def room_delete(db, room_id):
    room = get(db, CinemaRoom, room_id, lock=True)
    if db.exec(select(Showtime.id).where(Showtime.room_id == room_id).limit(1)).first():
        raise HTTPException(409, "Phòng đã có lịch chiếu, không thể xóa")
    room.deleted_at = utcnow()
    save(db, room)
    return {"message": "Đã xóa phòng"}


def seat_unused(db, seat_id):
    if db.exec(select(BookingDetail.id).where(BookingDetail.seat_id == seat_id).limit(1)).first():
        raise HTTPException(409, "Ghế đã có đơn đặt vé, không thể sửa hoặc xóa")
    if db.exec(select(SeatStatus.id).where(SeatStatus.seat_id == seat_id,
        SeatStatus.status.in_(["HOLD", "BOOKED"])).limit(1)).first():
        raise HTTPException(409, "Ghế đang được giữ hoặc đã bán")


def seat_write(db, room_id, body, seat_id=None):
    room = get(db, CinemaRoom, room_id, lock=True)
    if room.status != "ACTIVE":
        raise HTTPException(409, "Phòng không hoạt động")
    seat_type = get(db, SeatType, body.seat_type_id)
    if seat_type.room_id != room_id:
        raise HTTPException(400, "Loại ghế phải thuộc phòng đang chọn")
    seat = get(db, Seat, seat_id, lock=True) if seat_id else Seat(room_id=room_id)
    if seat_id:
        if seat.room_id != room_id:
            raise HTTPException(404, "Ghế không thuộc phòng đang chọn")
        seat_unused(db, seat_id)
    else:
        count = db.exec(select(func.count(Seat.id)).where(Seat.room_id == room_id)).one()
        if count >= room.capacity:
            raise HTTPException(409, "Phòng đã đủ sức chứa")
    if db.exec(select(Seat.id).where(Seat.room_id == room_id, Seat.seat_name == body.seat_name,
        Seat.id != (seat_id or 0))).first():
        raise HTTPException(409, "Vị trí ghế đã tồn tại")
    seat.seat_name, seat.seat_type_id = body.seat_name, body.seat_type_id
    return save(db, seat)


def seat_delete(db, room_id, seat_id):
    get(db, CinemaRoom, room_id, lock=True)
    seat = get(db, Seat, seat_id, lock=True)
    if seat.room_id != room_id:
        raise HTTPException(404, "Ghế không thuộc phòng đang chọn")
    seat_unused(db, seat_id)
    db.exec(delete(SeatStatus).where(SeatStatus.seat_id == seat_id))
    return remove(db, seat)


def show_unused(db, showtime_id):
    if db.exec(select(Booking.id).where(Booking.showtime_id == showtime_id).limit(1)).first():
        raise HTTPException(409, "Suất chiếu đã có đơn đặt vé, không thể sửa hoặc xóa")
    if db.exec(select(SeatStatus.id).where(SeatStatus.showtime_id == showtime_id,
        SeatStatus.status.in_(["HOLD", "BOOKED"])).limit(1)).first():
        raise HTTPException(409, "Suất chiếu đang có ghế được giữ hoặc đã bán")


def showtime_write(db, body, showtime_id=None):
    # Film lock serializes metadata changes; the room lock serializes all schedule writers.
    film = get(db, Film, body.film_id, lock=True)
    previous = get(db, Showtime, showtime_id) if showtime_id else None
    for room_id in sorted({body.room_id, previous.room_id if previous else body.room_id}):
        get(db, CinemaRoom, room_id, lock=True)
    room = get(db, CinemaRoom, body.room_id)
    get(db, Theater, room.theater_id)
    show = get(db, Showtime, showtime_id, lock=True) if showtime_id else Showtime()
    if showtime_id:
        show_unused(db, showtime_id)
    if room.status != "ACTIVE":
        raise HTTPException(409, "Phòng không hoạt động")
    if not db.get(FilmFormat, (body.film_id, body.format_id)):
        raise HTTPException(400, "Phim không hỗ trợ định dạng đã chọn")
    if film.release_date and body.show_date < film.release_date or film.end_date and body.show_date > film.end_date:
        raise HTTPException(400, "Ngày chiếu ngoài thời gian phát hành phim")
    start = datetime.combine(body.show_date, body.start_time)
    end = datetime.combine(body.show_date, body.end_time)
    if start <= datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).replace(tzinfo=None):
        raise HTTPException(400, "Suất chiếu phải ở tương lai")
    if not film.duration_minutes or (end-start).total_seconds() < film.duration_minutes*60:
        raise HTTPException(400, "Khoảng chiếu phải đủ thời lượng phim")
    conflict = db.exec(select(Showtime.id).where(Showtime.room_id == body.room_id,
        Showtime.show_date == body.show_date, Showtime.status != "CANCELLED",
        Showtime.start_time < body.end_time, Showtime.end_time > body.start_time,
        Showtime.id != (showtime_id or 0))).first()
    if conflict:
        raise HTTPException(409, "Lịch chiếu bị trùng trong phòng. Vui lòng chọn lại thời gian.")
    for key, value in body.model_dump().items():
        setattr(show, key, value)
    return save(db, show)


def showtime_delete(db, showtime_id):
    show = get(db, Showtime, showtime_id)
    get(db, CinemaRoom, show.room_id, lock=True)
    show = get(db, Showtime, showtime_id, lock=True)
    show_unused(db, showtime_id)
    db.exec(delete(SeatStatus).where(SeatStatus.showtime_id == showtime_id))
    return remove(db, show)


def price_write(db, body, price_id=None):
    get(db, CinemaRoom, body.room_id, lock=True)
    price = get(db, SeatType, price_id, lock=True) if price_id else SeatType()
    if price_id and price.room_id != body.room_id:
        raise HTTPException(400, "Không thể chuyển loại ghế sang phòng khác")
    for key, value in body.model_dump().items():
        setattr(price, key, value)
    # BookingDetail.price is a snapshot and must never be updated here.
    return save(db, price)


def employee_create(db, body):
    role = get(db, Role, body.role_id)
    if role.code not in ("ADMIN", "MANAGER", "STAFF"):
        raise HTTPException(400, "Chọn vai trò nhân viên, quản lý hoặc quản trị viên")
    user = User(**body.model_dump(exclude={"password"}), password=hash_password(body.password))
    return save(db, user)


def employee_write(db, user_id, body):
    user = get(db, User, user_id, lock=True)
    for key, value in body.model_dump().items():
        setattr(user, key, value)
    return save(db, user)


def account_status(db, user_id, body, admin):
    user = get(db, User, user_id, lock=True)
    if user.id == admin.id and not body.is_active:
        raise HTTPException(409, "Không thể tự khóa tài khoản đang đăng nhập")
    user.is_active = body.is_active
    return save(db, user)


def document_detail(db, document_id):
    doc = get(db, KnowledgeDocument, document_id)
    chunks = db.exec(select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id)
        .order_by(KnowledgeChunk.id)).all()
    return {**doc.model_dump(), "chunks": [dict(id=c.id, content=c.content,
        embedding_version=c.embedding_version) for c in chunks]}


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def document_write(db, body):
    # PostgreSQL advisory lock also serializes creation when the source does not exist yet.
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:source, 0))"), {"source": body.source_id})
    doc = db.exec(select(KnowledgeDocument).where(KnowledgeDocument.source_id == body.source_id)
        .with_for_update()).first()
    if doc and (body.expected_updated_at is None or utc(doc.updated_at) != utc(body.expected_updated_at)):
        raise HTTPException(409, "Tài liệu đã thay đổi; tải lại trước khi cập nhật")
    data = body.model_dump(exclude={"expected_updated_at"})
    data["approved"] = False
    try:
        doc = upsert_document(db, data)
        db.refresh(doc)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Nguồn tài liệu đã được cập nhật bởi người khác")
    except Exception:
        db.rollback()
        raise
    return doc


def document_approve(db, document_id, body):
    doc = get(db, KnowledgeDocument, document_id, lock=True)
    if doc.version != body.version or utc(doc.updated_at) != utc(body.expected_updated_at):
        raise HTTPException(409, "Phiên bản tài liệu đã thay đổi; cần xem và duyệt lại")
    chunks = db.exec(select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id)).all()
    if body.approved and (not chunks or any(c.embedding_version != EMBEDDING_VERSION or not c.embedding for c in chunks)):
        raise HTTPException(409, "Tài liệu chưa xử lý xong")
    doc.approved, doc.updated_at = body.approved, utcnow()
    return save(db, doc)


def document_delete(db, document_id):
    doc = get(db, KnowledgeDocument, document_id, lock=True)
    db.exec(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))
    return remove(db, doc)
