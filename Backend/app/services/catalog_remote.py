"""Typed Catalog contracts; source archive is never a service-mode fallback."""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from app.core.config import settings
from app.utils.catalog_ownership import get_owner


class FilmFact(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int = Field(gt=0)
    title: str
    image: str | None = None
    rating: str | None = None
    duration_minutes: int | None = None
    language: str | None = None
    subtitle: str | None = None
    release_date: date | None = None
    end_date: date | None = None
    description: str | None = None
    trailer: str | None = None
    deleted_at: datetime | None = None
    catalog_version: int = Field(ge=1)
    genre: str | None = None
    formats: list[str] = []
    duration: str | None = None
    genre_ids: list[int] = []
    format_ids: list[int] = []
    format_name: str | None = None


class QuoteLine(BaseModel):
    food_item_id: int = Field(gt=0)
    name: str
    category: str
    quantity: int = Field(ge=1, le=20)
    unit_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    catalog_version: int = Field(ge=1)
    components: list[dict]


class Quote(BaseModel):
    id: UUID
    version: int = Field(ge=1)
    lines: list[QuoteLine]
    total: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(pattern="^VND$")
    expires_at: datetime


class QuotedLines(list):
    def __init__(self, quote):
        super().__init__(line.model_dump(exclude={"catalog_version"}) for line in quote.lines)
        self.quote = quote


def call(method, path, **kwargs):
    if len(settings.INTERNAL_SERVICE_KEY) < 32:
        raise HTTPException(503, "Catalog service credential is not configured")
    try:
        with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
            response = client.request(method, settings.CATALOG_SERVICE_ORIGIN+path,
                headers={"X-Service-Key": settings.INTERNAL_SERVICE_KEY}, **kwargs)
        if response.status_code in {400, 404, 409, 422}:
            raise HTTPException(response.status_code, "Catalog từ chối dữ liệu hoặc tham chiếu")
        if response.status_code != 200:
            raise HTTPException(503, "Catalog unavailable")
        return response.json()
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(503, "Catalog unavailable") from exc


def film_batch(ids, *, include_retired=False):
    ids = sorted(set(ids))
    result = {}
    try:
        for start in range(0, len(ids), 200):
            rows = call("POST", "/internal/v1/films/batch", json={"ids": ids[start:start+200], "include_retired": include_retired})
            for row in rows:
                film = FilmFact.model_validate(row)
                if film.id not in ids or film.id in result:
                    raise ValueError("Unexpected Catalog ID")
                result[film.id] = film
        return result
    except (ValidationError, ValueError, TypeError) as exc:
        raise HTTPException(503, "Invalid Catalog facts") from exc


def get_film(db, film_id, *, include_retired=False):
    owner = get_owner(db)
    if owner == "maintenance":
        raise HTTPException(503, "Catalog đang chuyển dữ liệu")
    if owner == "service":
        return film_batch([film_id], include_retired=include_retired).get(film_id)
    from app.models import Film
    film = db.get(Film, film_id)
    return film if film and (include_retired or not film.deleted_at) else None


def show_film(db, show, booking=None):
    if get_owner(db) in {"service", "maintenance"}:
        snapshot = booking.catalog_film_snapshot if booking and booking.catalog_film_snapshot else show.catalog_film_snapshot
        try:
            fact = FilmFact.model_validate(snapshot)
            if fact.id != show.film_id:
                raise ValueError("Wrong film snapshot")
            return fact
        except (ValidationError, ValueError) as exc:
            raise HTTPException(503, "Missing historical Catalog snapshot") from exc
    return get_film(db, show.film_id, include_retired=True)


def binding(body):
    from fastapi.encoders import jsonable_encoder
    payload = body.model_dump(exclude={"room_id"})
    payload["id"] = str(uuid4())
    result = call("POST", "/internal/v1/schedule-bindings", json=jsonable_encoder(payload))
    try:
        if str(UUID(result["id"])) != payload["id"]:
            raise ValueError("Unexpected binding")
        fact = FilmFact.model_validate(result["film_snapshot"])
        if fact.id != body.film_id or body.format_id not in fact.format_ids or not fact.format_name:
            raise ValueError("Invalid binding snapshot")
        return result
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise HTTPException(503, "Invalid Catalog binding") from exc


def quote(selections):
    try:
        result = Quote.model_validate(call("POST", "/internal/v1/food-quotes", json={"selections": [s.model_dump() for s in selections]}))
        expected = {s.food_item_id: s.quantity for s in selections}
        actual = {line.food_item_id: line.quantity for line in result.lines}
        if expected != actual or len(actual) != len(result.lines) or sum((line.unit_price*line.quantity for line in result.lines), Decimal("0")) != result.total:
            raise ValueError("Quote lines do not match requested items")
        if result.expires_at.tzinfo is None or result.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(409, "Quote đã hết hạn")
        return QuotedLines(result), result.total
    except (ValidationError, ValueError, TypeError) as exc:
        raise HTTPException(503, "Invalid Catalog quote") from exc
