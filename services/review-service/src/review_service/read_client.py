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

    def direct(self,origin,method,path,**kwargs):
        if len(self.settings.service_key)<32:raise HTTPException(503,"Review read credential missing")
        try:
            reply=self.http.request(method,origin+path,headers={"X-Service-Key":self.settings.service_key},timeout=5,follow_redirects=False,**kwargs)
            if reply.status_code==404:raise HTTPException(404,"Phim không tồn tại")
            reply.raise_for_status();return reply.json()
        except (httpx.HTTPError,ValueError) as exc:raise HTTPException(503,"Không thể tra cứu dữ liệu owner") from exc

    def batch(self,ids):
        return [row for start in range(0,len(ids),200) for row in self.direct(self.settings.catalog_origin,'POST','/internal/v1/films/batch',json={'ids':ids[start:start+200],'include_retired':False})]

    def request(self, method, path, **kwargs):
        if self.settings.direct_reads_enabled:
            if path.startswith('films/'):
                rows=self.batch([int(path.split('/')[1])])
                if not rows:raise HTTPException(404,"Phim không tồn tại")
                return rows[0]
            if path=='candidates':
                ids=self.direct(self.settings.booking_origin,'GET','/internal/v1/booking-read/candidates',**kwargs)
                return self.batch(ids)
            if path=='authors':
                items=kwargs['json']['items']
                profiles=self.direct(self.settings.identity_origin,'POST','/internal/v1/users/profiles',json={'user_ids':sorted({r['user_id'] for r in items})})
                verified=self.direct(self.settings.booking_origin,'POST','/internal/v1/booking-read/verified',json={'items':items})
                names={r['id']:r['username'] for r in profiles};proof={(r['user_id'],r['film_id']):r['verified_purchase'] for r in verified}
                if set(proof)!={(r['user_id'],r['film_id']) for r in items}:raise HTTPException(503,'Incomplete purchase evidence')
                return [{**r,'author':names.get(r['user_id'],'Khán giả'),'verified_purchase':proof[(r['user_id'],r['film_id'])]} for r in items]
            raise ValueError('Unsupported direct read')
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
