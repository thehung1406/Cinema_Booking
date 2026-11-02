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

    def post(self, path, payload):
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
