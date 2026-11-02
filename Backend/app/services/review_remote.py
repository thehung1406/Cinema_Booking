"""Temporary HTTP adapter for AI and reporting after Review ownership moves."""
import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from app.core.config import settings


class Sentiments(BaseModel):
    positive: int = Field(ge=0)
    neutral: int = Field(ge=0)
    negative: int = Field(ge=0)
    total: int = Field(ge=0)
    pending: int = Field(ge=0)
    coverage: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def counts(self):
        if self.positive + self.neutral + self.negative + self.pending != self.total:
            raise ValueError("Inconsistent sentiment totals")
        return self


def request(method, path, **kwargs):
    if len(settings.INTERNAL_SERVICE_KEY) < 32:
        raise HTTPException(503, "Review service credential missing")
    try:
        origin = httpx.URL(settings.REVIEW_SERVICE_ORIGIN)
        if origin.scheme not in {"http", "https"} or not origin.host or origin.userinfo or origin.path != "/" or origin.query or origin.fragment:
            raise ValueError("Fixed Review origin required")
        with httpx.Client(trust_env=False, timeout=5, follow_redirects=False) as client:
            reply = client.request(method, str(origin).rstrip("/") + "/internal/v1/" + path,
                headers={"X-Service-Key": settings.INTERNAL_SERVICE_KEY}, **kwargs)
            reply.raise_for_status()
            return reply.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Review Service tạm không khả dụng") from exc


def positive_films(theater_id, show_date, window_days, limit, evening):
    params = {"window_days": window_days or settings.SENTIMENT_WINDOW_DAYS, "limit": limit, "evening": str(evening).lower()}
    if theater_id is not None:
        params["theater_id"] = theater_id
    if show_date is not None:
        params["show_date"] = show_date.isoformat()
    rows = request("GET", "positive-films", params=params)
    if not isinstance(rows, list) or len(rows) > limit or any(not isinstance(r, dict) or
            not {"film_id", "title", "image", "summary", "booking_url"} <= r.keys() or
            r["booking_url"] != f"/ticket-booking?filmId={r['film_id']}" for r in rows):
        raise HTTPException(503, "Invalid Review ranking response")
    return rows


def report(start_date, end_date, film_ids):
    try:
        return Sentiments.model_validate(request("POST", "report-sentiments", json={
            "start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "film_ids": film_ids})).model_dump()
    except ValueError as exc:
        raise HTTPException(503, "Invalid Review report response") from exc
