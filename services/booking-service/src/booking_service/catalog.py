"""Typed Catalog contracts; source archive is never a service-mode fallback."""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from .config import settings


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
    if len(settings.service_key) < 32:
        raise HTTPException(503, "Catalog service credential is not configured")
    try:
        with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
            response = client.request(method, settings.catalog_origin+path,
                headers={"X-Service-Key": settings.service_key}, **kwargs)
        if response.status_code in {400, 404, 409, 422}:
            raise HTTPException(response.status_code, "Catalog từ chối dữ liệu hoặc tham chiếu")
        if response.status_code != 200:
            raise HTTPException(503, "Catalog unavailable")
        return response.json()
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(503, "Catalog unavailable") from exc


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
