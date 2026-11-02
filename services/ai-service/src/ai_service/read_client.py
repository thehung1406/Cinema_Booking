"""Typed, fixed-origin read-only allowlist. Never forwards SQL or model-generated calls."""

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError


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

    def call(self,origin,method,path,**kwargs):
        if len(self.settings.service_key)<32:raise HTTPException(503,'AI read credential missing')
        try:
            response=self.http.request(method,origin+path,headers={'X-Service-Key':self.settings.service_key},timeout=5,follow_redirects=False,**kwargs)
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
        if len(self.settings.service_key) < 32:
            raise HTTPException(503, "AI read adapter is not configured")
        try:
            response = self.http.post(self.settings.read_origin + "/internal/v1/ai-read/" + path,
                headers={"X-Service-Key": self.settings.service_key}, json=payload, timeout=5, follow_redirects=False)
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
