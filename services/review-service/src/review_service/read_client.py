import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError


class FilmFact(BaseModel):
    id: int = Field(gt=0)
    title: str
    image: str | None = None


class AuthorFact(BaseModel):
    user_id: int
    film_id: int
    author: str
    verified_purchase: bool


class ReadClient:
    def __init__(self, http, settings):
        self.http, self.settings = http, settings

    def request(self, method, path, **kwargs):
        if len(self.settings.service_key) < 32:
            raise HTTPException(503, "Review read credential is not configured")
        try:
            reply = self.http.request(method, self.settings.read_origin + "/internal/v1/review-read/" + path,
                headers={"X-Service-Key": self.settings.service_key}, timeout=5, follow_redirects=False, **kwargs)
            if reply.status_code == 404:
                raise HTTPException(404, "Phim không tồn tại")
            reply.raise_for_status()
            return reply.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "Không thể tra cứu dữ liệu phim/người dùng") from exc

    def film(self, film_id):
        try:
            return FilmFact.model_validate(self.request("GET", f"films/{film_id}"))
        except ValidationError as exc:
            raise HTTPException(503, "Invalid film fact") from exc

    def authors(self, reviews):
        if not reviews:
            return {}
        keys = {(r.user_id, r.film_id) for r in reviews}
        try:
            rows = [AuthorFact.model_validate(r) for r in self.request("POST", "authors", json={"items": [
                {"user_id": u, "film_id": f} for u, f in sorted(keys)]})]
            result = {(r.user_id, r.film_id): r for r in rows}
            if set(result) != keys:
                raise ValueError("Missing author facts")
            return result
        except (ValidationError, ValueError) as exc:
            raise HTTPException(503, "Invalid author facts") from exc

    def candidates(self, theater_id=None, show_date=None, evening=False):
        params = {"evening": str(evening).lower()}
        if theater_id is not None:
            params["theater_id"] = theater_id
        if show_date is not None:
            params["show_date"] = show_date.isoformat()
        try:
            return [FilmFact.model_validate(r) for r in self.request("GET", "candidates", params=params)]
        except (ValidationError, TypeError) as exc:
            raise HTTPException(503, "Invalid candidate facts") from exc
