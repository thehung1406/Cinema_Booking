"""Apply hard constraints before pagination, using live seats and immutable prices."""
from datetime import datetime
from decimal import Decimal
import unicodedata
import re
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from .reservations import availability, now
from .sales import future_query


def fold(text):
    return "".join(c for c in unicodedata.normalize("NFD", str(text or "").lower().replace("đ", "d"))
                   if unicodedata.category(c) != "Mn")


def city_key(value):
    key = re.sub(r"[^a-z0-9]", "", fold(value))
    aliases = {"tphcm": "hochiminh", "hcm": "hochiminh", "saigon": "hochiminh",
               "tphochiminh": "hochiminh", "thanhphohochiminh": "hochiminh", "hanoi": "hanoi", "tphanoi": "hanoi"}
    return aliases.get(key, key)


def discover(db, body):
    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    if body.show_date < today:
        raise HTTPException(422, "Vui lòng chọn ngày hiện tại hoặc tương lai")
    query = future_query(body.film_id, body.theater_id, body.show_date)
    result, matched = [], 0
    # Iterate in showtime order. Stop only after enough *eligible* items, not before budget/availability filters.
    for config in db.scalars(query.execution_options(yield_per=100)):
        film, theater = config.snapshot["film"], config.snapshot["theater"]
        filters = [(body.film_name, film.get("title")), (body.theater_name, theater.get("name")),
                   (body.genre, film.get("genre")),
                   (body.language, film.get("language")), (body.format, film.get("format_name"))]
        if any(needle and fold(needle) not in fold(value) for needle, value in filters):
            continue
        if body.city and city_key(body.city) != city_key(theater.get("city")):
            continue
        if body.duration_max and (not film.get("duration_minutes") or film["duration_minutes"] > body.duration_max):
            continue
        if body.start_after and config.start_time < body.start_after:
            continue
        if body.start_before and config.start_time > body.start_before:
            continue
        statuses = availability(db, config.showtime_id)
        available = {seat["seat_id"] for seat in statuses if seat["status"] == "AVAILABLE"}
        prices = sorted(Decimal(str(seat["price"])) for seat in config.snapshot["seats"]
                        if seat["id"] in available and seat["status"] == "ACTIVE")
        eligible = [price for price in prices if body.budget_per_ticket is None or price <= body.budget_per_ticket]
        if len(eligible) < body.party_size:
            continue
        minimum_total = sum(eligible[:body.party_size], Decimal("0"))
        if body.budget_total is not None and minimum_total > body.budget_total:
            continue
        matched += 1
        if matched <= body.offset:
            continue
        if len(result) == body.limit:
            return dict(items=result, has_more=True, next_offset=body.offset+body.limit, as_of=now())
        result.append(dict(showtime_id=config.showtime_id, sales_version=config.sales_version,
            film_id=config.film_id, film_title=film["title"], image=film.get("image"),
            genre=film.get("genre"), duration_minutes=film.get("duration_minutes"),
            language=film.get("language"), rating=film.get("rating"),
            theater_id=config.theater_id, theater_name=theater["name"], city=theater.get("city"),
            room_name=config.snapshot["room"]["name"], show_date=config.show_date,
            start_time=config.start_time, format=film.get("format_name"),
            available_seats=len(available), min_ticket_price=str(eligible[0]),
            minimum_total=str(minimum_total), party_size=body.party_size, currency="VND",
            adjacent_seats_guaranteed=False, url=f"/seat-selection/{config.showtime_id}"))
    return dict(items=result, has_more=False, next_offset=None, as_of=now())
