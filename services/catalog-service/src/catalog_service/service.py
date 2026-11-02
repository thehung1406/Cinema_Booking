from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .models import Film, Genre, Format, FoodItem, ComboItem, FoodQuote, ScheduleBinding, utcnow


def film_data(film):
    fields = [c.name for c in Film.__table__.columns]
    return {**{key: getattr(film, key) for key in fields}, "genre": film.genre, "formats": film.formats,
            "duration": film.duration, "genre_ids": [g.id for g in film.genre_items],
            "format_ids": [f.id for f in film.format_items]}


def get_film(db, film_id, *, lock=False, include_retired=False):
    query = select(Film).where(Film.id == film_id)
    if lock:
        query = query.with_for_update()
    film = db.scalar(query)
    if film is None or (film.deleted_at is not None and not include_retired):
        raise HTTPException(404, "Phim không tồn tại")
    return film


def save(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Dữ liệu trùng hoặc đang được sử dụng") from None


def film_write(db, body, film_id=None):
    film = get_film(db, film_id, lock=True) if film_id else Film(catalog_version=0)
    genres = list(db.scalars(select(Genre).where(Genre.id.in_(set(body.genre_ids)))))
    formats = list(db.scalars(select(Format).where(Format.id.in_(set(body.format_ids)))))
    if len(genres) != len(set(body.genre_ids)) or len(formats) != len(set(body.format_ids)):
        raise HTTPException(400, "Thể loại hoặc định dạng không tồn tại")
    if film_id:
        bindings = db.scalars(select(ScheduleBinding).where(ScheduleBinding.film_id == film_id, ScheduleBinding.reference_state != "RELEASED"))
        for binding in bindings:
            minutes = (datetime.combine(binding.show_date, binding.end_time)-datetime.combine(binding.show_date, binding.start_time)).total_seconds()/60
            if binding.format_id not in body.format_ids:
                raise HTTPException(409, "Không thể bỏ định dạng đã công bố cho lịch chiếu")
            if binding.status == "ACTIVE" and (not body.release_date <= binding.show_date <= body.end_date or minutes < body.duration_minutes):
                raise HTTPException(409, "Phim đã có tham chiếu lịch chiếu không phù hợp thay đổi")
    for key, value in body.model_dump(exclude={"genre_ids", "format_ids"}).items():
        setattr(film, key, value)
    film.genre_items, film.format_items = genres, formats
    film.catalog_version += 1
    db.add(film)
    save(db)
    return film


def retire_film(db, film_id):
    film = get_film(db, film_id, lock=True)
    if db.scalar(select(ScheduleBinding.id).where(ScheduleBinding.film_id == film_id, ScheduleBinding.reference_state != "RELEASED").limit(1)):
        raise HTTPException(409, "Phim đã có lịch hoặc tham chiếu đang chờ; không thể ngừng hoạt động")
    film.deleted_at, film.catalog_version = utcnow(), film.catalog_version + 1
    save(db)
    return {"message": "Đã xóa phim"}


def bind_schedule(db, body):
    from sqlalchemy import text
    from .models import BindingClosure
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:id,1))"),{"id":str(body.id)})
    if db.get(BindingClosure,str(body.id)): raise HTTPException(409,"Tham chiếu đã kết thúc")
    # This same Film lock serializes grants, retirement and metadata/format changes.
    film = get_film(db, body.film_id, lock=True)
    existing = db.get(ScheduleBinding, str(body.id))
    fields = body.model_dump(exclude={"id"})
    if existing:
        if existing.reference_state == "RELEASED":
            raise HTTPException(409, "Tham chiếu đã kết thúc; không thể tái sử dụng")
        if any(getattr(existing, key) != value for key, value in fields.items()):
            raise HTTPException(409, "Binding ID đã được dùng cho lịch khác")
        return existing
    fmt = next((f for f in film.format_items if f.id == body.format_id), None)
    minutes = (datetime.combine(body.show_date, body.end_time)-datetime.combine(body.show_date, body.start_time)).total_seconds()/60
    if fmt is None:
        raise HTTPException(400, "Phim không hỗ trợ định dạng đã chọn")
    if (film.release_date and body.show_date < film.release_date) or (film.end_date and body.show_date > film.end_date):
        raise HTTPException(400, "Ngày chiếu ngoài thời gian phát hành phim")
    if not film.duration_minutes or minutes < film.duration_minutes:
        raise HTTPException(400, "Khoảng chiếu phải đủ thời lượng phim")
    snapshot = film_data(film)
    # JSON stores dates/times explicitly; snapshots are never patched by later edits.
    from fastapi.encoders import jsonable_encoder
    snapshot = jsonable_encoder({**snapshot, "format_name": fmt.name})
    binding = ScheduleBinding(id=str(body.id), **fields, film_version=film.catalog_version, film_snapshot=snapshot)
    db.add(binding)
    save(db)
    return binding


def menu(db):
    # Quote and future menu writers share this transaction advisory lock. A full
    # menu snapshot therefore cannot mix prices/components from two edits.
    from sqlalchemy import text
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(78433266)"))
    items = list(db.scalars(select(FoodItem).order_by(FoodItem.id)))
    by_id = {item.id: item for item in items}
    parts = {}
    for part in db.scalars(select(ComboItem).order_by(ComboItem.id)):
        parts.setdefault(part.combo_id, []).append(part)
    result = []
    for item in items:
        components = parts.get(item.id, [])
        if not item.is_active:
            continue
        if item.category == "COMBO" and (not components or any(
            p.food_item_id not in by_id or not by_id[p.food_item_id].is_active or
            by_id[p.food_item_id].category == "COMBO" for p in components)):
            continue
        result.append(dict(id=item.id, name=item.name, description=item.description, category=item.category,
            price=item.price, catalog_version=item.catalog_version,
            components=[dict(food_item_id=p.food_item_id, name=by_id[p.food_item_id].name, quantity=p.quantity) for p in components]))
    return result


def quote(db, selections, settings):
    ids = [s.food_item_id for s in selections]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "Danh sách bỏng, nước và combo bị trùng")
    catalog = {item["id"]: item for item in menu(db)}
    lines, total = [], Decimal("0")
    for selection in selections:
        item = catalog.get(selection.food_item_id)
        if item is None:
            raise HTTPException(409, "Món hoặc combo đã ngừng bán")
        lines.append(dict(food_item_id=item["id"], name=item["name"], category=item["category"],
            quantity=selection.quantity, unit_price=str(item["price"]), catalog_version=item["catalog_version"],
            components=item["components"]))
        total += item["price"] * selection.quantity
    if total >= Decimal("10000000000"):
        raise HTTPException(400, "Tổng quote vượt giới hạn thanh toán")
    row = FoodQuote(id=str(uuid4()), version=1, lines=lines, total=total,
                    expires_at=utcnow()+timedelta(seconds=settings.quote_seconds))
    db.add(row)
    save(db)
    return row


def quote_data(row):
    return dict(id=row.id, version=row.version, lines=row.lines, total=str(row.total),
                currency="VND", expires_at=row.expires_at)


def food_write(db, body, food_id=None):
    menu(db)  # Serializes edits with quote snapshot construction.
    item = db.get(FoodItem, food_id) if food_id else FoodItem(catalog_version=0)
    if item is None:
        raise HTTPException(404, "Món không tồn tại")
    for part in body.components:
        component = db.get(FoodItem, part.food_item_id)
        if component is None or component.id == food_id or component.category == "COMBO" or not component.is_active:
            raise HTTPException(400, "Thành phần combo phải là món đang bán")
    if food_id and body.category == "COMBO" and db.scalar(select(ComboItem.id).where(ComboItem.food_item_id == food_id).limit(1)):
        raise HTTPException(409, "Không thể đổi thành combo khi món là thành phần combo khác")
    for key, value in body.model_dump(exclude={"components"}).items():
        setattr(item, key, value)
    item.catalog_version += 1
    db.add(item)
    db.flush()
    from sqlalchemy import delete
    db.execute(delete(ComboItem).where(ComboItem.combo_id == item.id))
    db.add_all([ComboItem(combo_id=item.id, food_item_id=p.food_item_id, quantity=p.quantity) for p in body.components])
    save(db)
    return {"id": item.id, "catalog_version": item.catalog_version}
