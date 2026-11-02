"""Gateway-only settings, independent of the monolith's environment."""

import httpx
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from .routing import DOMAINS


class GatewaySettings(BaseSettings):
    legacy_enabled: bool = True
    monolith_url: str = "http://127.0.0.1:8000"
    connect_timeout_seconds: float = Field(default=3, gt=0, le=30)
    read_timeout_seconds: float = Field(default=30, gt=0, le=300)
    max_connections: int = Field(default=100, ge=1, le=1000)
    upstreams: dict[str, str] = Field(default_factory=dict)
    enabled_domains: list[str] = Field(default_factory=list)
    required_domains: list[str] = Field(default_factory=list)

    model_config = SettingsConfigDict(
        env_prefix="GATEWAY_", env_file="gateway/.env", extra="ignore"
    )

    @field_validator("monolith_url")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        url = httpx.URL(value)
        if (
            url.scheme not in {"http", "https"}
            or not url.host
            or url.userinfo
            or url.path not in {"", "/"}
            or url.query
            or url.fragment
        ):
            raise ValueError("GATEWAY_MONOLITH_URL must be an HTTP(S) origin without credentials/path/query")
        return str(url).rstrip("/")

    def timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            self.read_timeout_seconds,
            connect=self.connect_timeout_seconds,
            pool=self.connect_timeout_seconds,
        )

    @model_validator(mode="after")
    def validate_domain_routes(self):
        if set(self.upstreams) - DOMAINS or set(self.enabled_domains) - DOMAINS or set(self.required_domains) - DOMAINS:
            raise ValueError("Unknown gateway domain")
        for origin in self.upstreams.values():
            self.validate_origin(origin)
        if set(self.enabled_domains) - set(self.upstreams):
            raise ValueError("Every enabled domain requires a configured upstream")
        if set(self.required_domains) - set(self.enabled_domains):
            raise ValueError("Required domains must also be enabled")
        self.upstreams = {domain: origin.rstrip("/") for domain, origin in self.upstreams.items()}
        return self

    def origin_for(self, domain):
        return self.upstreams[domain] if domain in self.enabled_domains else self.monolith_url
