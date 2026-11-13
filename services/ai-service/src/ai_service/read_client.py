"""Typed, fixed-origin read-only allowlist. Never forwards SQL or model-generated calls."""

from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import time
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from .rag import folded
from .schemas import ToolCall


LEGACY_CONTEXT_FIELDS = {"film_id", "theater_id", "show_date", "showtime_id"}
FILM_LIST_LIMIT = 12


class Entity(BaseModel):
    id: int = Field(gt=0)
    name: str


class Matches(BaseModel):
    film_id: list[Entity]
    theater_id: list[Entity]


class Names(BaseModel):
    film_name: str | None
    theater_name: str | None


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    text: str
    url: str
    kind: str
    version: str | None = None


class ReadSession:
    def __init__(self, http, settings):
        self.http, self.settings = http, settings
        self.context_cache = {}
        self.deadline = time.monotonic() + 20

    def call(self,origin,method,path,**kwargs):
        if len(self.settings.service_key)<32:raise HTTPException(503,'AI read credential missing')
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise HTTPException(503, 'AI request deadline exceeded')
        try:
            response=self.http.request(method,origin+path,headers={'X-Service-Key':self.settings.service_key},timeout=min(5,remaining),follow_redirects=False,**kwargs)
            if response.status_code in {404,422}:raise HTTPException(422,'Ngữ cảnh không hợp lệ')
            response.raise_for_status();return response.json()
        except (httpx.HTTPError,ValueError) as exc:raise HTTPException(503,'Không thể tra cứu dữ liệu owner') from exc

    def direct(self,path,payload):
        from datetime import datetime,date
        from zoneinfo import ZoneInfo
        cfg=self.settings
        def films(ids):return self.call(cfg.catalog_origin,'POST','/internal/v1/films/batch',json={'ids':ids,'include_retired':False})
        if path=='matches':return dict(film_id=self.call(cfg.catalog_origin,'POST','/internal/v1/films/matches',json=payload),theater_id=self.call(cfg.cinema_origin,'POST','/internal/v1/theaters/matches',json=payload))
        if path=='context':
            film=films([payload['film_id']]) if payload.get('film_id') else None
            if film==[]:raise HTTPException(422,'Phim không tồn tại')
            theater=self.call(cfg.cinema_origin,'GET',f"/theaters/{payload['theater_id']}") if payload.get('theater_id') else None
            if payload.get('show_date') and date.fromisoformat(payload['show_date'])<datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date():raise HTTPException(422,'Vui lòng chọn ngày hiện tại hoặc tương lai')
            if payload.get('showtime_id'):self.call(cfg.booking_origin,'POST','/internal/v1/booking-read/context',json=payload)
            return dict(film_name=film[0]['title'] if film else None,theater_name=theater['name'] if theater else None)
        if path!='tool':raise ValueError('Unsupported AI read')
        call=payload['call'];context=call.get('context') or {};name=call['name'];self.direct('context',context)
        if name in {'get_showtimes','get_ticket_prices','get_seat_availability'}:return self.call(cfg.booking_origin,'POST','/internal/v1/booking-read/tool',json=payload)
        if name=='search_films':
            rows=films([context['film_id']]) if context.get('film_id') else self.call(cfg.catalog_origin,'POST','/internal/v1/films/search',json={'q':call.get('query','').strip(),'limit':8}) if call.get('query','').strip() else []
            return [dict(id=f"film:{f['id']}",title=f['title'],text=f"{f['title']}. Thể loại: {f.get('genre') or 'chưa cập nhật'}. {f.get('description') or 'Chưa có mô tả.'}",url=f"/movie/{f['id']}",kind='film') for f in rows]
        if name=='get_positive_films':
            rows=self.call(cfg.review_origin,'GET','/films/positive-trending',params={k:v for k,v in dict(theater_id=context.get('theater_id'),show_date=context.get('show_date'),evening=payload['evening']).items() if v is not None})
            return [dict(id=f"positive:{f['film_id']}",title=f['title'],text=f"{f['title']}: {f['summary']['positive_ratio']:.0%} tích cực trên {f['summary']['total']} đánh giá hợp lệ trong {f['summary']['window_days']} ngày; còn suất chiếu phù hợp. Xếp hạng theo cận dưới Wilson.",url=f['booking_url'],kind='live') for f in rows]
        raise HTTPException(422,'Công cụ không được phép')

    def post(self, path, payload):
        if self.settings.direct_reads_enabled:return self.direct(path,payload)
        if path == "context":
            payload = {field: payload[field] for field in LEGACY_CONTEXT_FIELDS}
        elif path == "tool":
            call = payload["call"]
            payload = payload | {"call": call | {
                "context": {field: call["context"][field] for field in LEGACY_CONTEXT_FIELDS},
            }}
        if len(self.settings.service_key) < 32:
            raise HTTPException(503, "AI read adapter is not configured")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise HTTPException(503, "AI request deadline exceeded")
        try:
            response = self.http.post(self.settings.read_origin + "/internal/v1/ai-read/" + path,
                headers={"X-Service-Key": self.settings.service_key}, json=payload,
                timeout=min(5, remaining), follow_redirects=False)
            if response.status_code == 422:
                raise HTTPException(422, response.json().get("detail", "Ngữ cảnh không hợp lệ"))
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "Không thể tra cứu dữ liệu rạp lúc này") from exc

    def matches(self, message):
        try:
            return Matches.model_validate(self.post("matches", {"message": message}))
        except ValidationError as exc:
            raise HTTPException(503, "Invalid business evidence") from exc

    def names(self, context):
        key = context.model_dump_json()
        if key not in self.context_cache:
            try:
                self.context_cache[key] = Names.model_validate(self.post("context", context.model_dump(mode="json")))
            except ValidationError as exc:
                raise HTTPException(503, "Invalid business context") from exc
        return self.context_cache[key]

    def showing_films(self, context):
        if not self.settings.direct_reads_enabled:
            films = self.legacy_film_list(context)
        elif context.show_date is None:
            films = self.call(self.settings.catalog_origin, "POST", "/internal/v1/films/search",
                              json={"now_showing": True, "limit": FILM_LIST_LIMIT + 1, "genre": context.genre})
        else:
            params = {"show_date": context.show_date.isoformat(), "evening": context.start_after is not None
                      and context.start_after.hour >= 18}
            if context.theater_id is not None:
                params["theater_id"] = context.theater_id
            ids = sorted(set(self.call(self.settings.booking_origin, "GET", "/internal/v1/booking-read/candidates", params=params)))
            films = []
            for offset in range(0, len(ids), 200):
                batch = self.call(self.settings.catalog_origin, "POST", "/internal/v1/films/batch",
                                  json={"ids": ids[offset:offset + 200], "include_retired": False})
                films.extend(film for film in batch if genre_matches(film, context.genre))
                if len(films) > FILM_LIST_LIMIT:
                    break
        return film_list_evidence(films)

    def upcoming_films(self, context):
        if self.settings.direct_reads_enabled:
            films = self.call(self.settings.catalog_origin, "POST", "/internal/v1/films/search",
                              json={"upcoming": True, "limit": FILM_LIST_LIMIT + 1, "genre": context.genre})
        else:
            films = self.legacy_film_list(context, upcoming=True)
        return film_list_evidence(films)

    def legacy_film_list(self, context, *, upcoming=False):
        origin = self.settings.read_origin
        scheduled = not upcoming and context.show_date is not None
        today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()
        page_size = 50
        offset, films = 0, []
        while len(films) <= FILM_LIST_LIMIT:
            rows = self.call(origin, "GET", "/films/", params={
                "now_showing": not upcoming and not scheduled, "skip": offset, "limit": page_size,
            })
            for film in rows:
                if not genre_matches(film, context.genre):
                    continue
                if upcoming and (film.get("release_date") or "") <= today:
                    continue
                if scheduled and not self.legacy_film_has_showtime(film["id"], context):
                    continue
                films.append(film)
                if len(films) > FILM_LIST_LIMIT:
                    break
            if len(rows) < page_size:
                break
            offset += page_size
        return films

    def legacy_film_has_showtime(self, film_id, context):
        if context.theater_id is not None:
            theater_ids = [context.theater_id]
        else:
            theaters = self.call(self.settings.read_origin, "GET", f"/theaters/by-film/{int(film_id)}",
                                 params={"from_date": context.show_date.isoformat()})
            theater_ids = [theater["id"] for theater in theaters]
        evening = context.start_after is not None and context.start_after.hour >= 18
        return any(self.run(ToolCall(name="get_showtimes", context=context.model_copy(update={
            "film_id": film_id, "theater_id": theater_id,
        })), evening) for theater_id in theater_ids)

    def run(self, call, evening):
        try:
            rows = self.post("tool", {"call": call.model_dump(mode="json"), "evening": evening})
            if not isinstance(rows, list) or len(rows) > 100:
                raise ValueError("Invalid tool result")
            result = [Evidence.model_validate(row) for row in rows]
            if any(not row.url.startswith("/") or row.url.startswith("//") or "\\" in row.url for row in result):
                raise ValueError("Invalid evidence link")
            return [row.model_dump(exclude_none=True) for row in result]
        except (ValueError, ValidationError) as exc:
            raise HTTPException(503, "Invalid business evidence") from exc


def genre_matches(film, genre):
    return not genre or folded(genre) in folded(film.get("genre") or "")


def film_list_evidence(films):
    evidence = []
    for film in films[:FILM_LIST_LIMIT]:
        film_id = int(film["id"])
        evidence.append(dict(id=f"film:{film_id}", title=film["title"], text=film["title"],
                             url=f"/movie/{film_id}", kind="film"))
    return evidence, len(films) > FILM_LIST_LIMIT
