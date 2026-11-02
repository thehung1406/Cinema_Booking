"""Fail-closed, uncached identity adapter; no JWT signing key in consumers."""

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Principal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(gt=0)
    role: str
    permissions: list[str]
    is_active: bool


class AuthError(Exception):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__("Identity validation failed")


class AuthClient:
    def __init__(self, client: httpx.AsyncClient, origin: str, service_key: str):
        url = httpx.URL(origin)
        if url.scheme not in {"http", "https"} or not url.host or url.userinfo or url.path != "/" or url.query or url.fragment:
            raise ValueError("Identity origin must be HTTP(S), without path/credentials")
        self.client, self.origin, self.service_key = client, str(url).rstrip("/"), service_key

    async def introspect(self, token: str, permission: str | None = None) -> Principal:
        if len(self.service_key) < 32:
            raise AuthError(503)
        try:
            response = await self.client.post(
                self.origin + "/internal/v1/auth/introspect",
                headers={"X-Service-Key": self.service_key}, json={"token": token},
                timeout=5, follow_redirects=False,
            )
            if response.status_code in {401, 403}:
                raise AuthError(response.status_code)
            if response.status_code != 200:
                raise AuthError(503)
            principal = Principal.model_validate(response.json())
        except (httpx.RequestError, ValidationError, ValueError) as exc:
            raise AuthError(503) from exc
        if not principal.is_active or (permission and permission not in principal.permissions):
            raise AuthError(403)
        return principal
