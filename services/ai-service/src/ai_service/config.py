import httpx
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    identity_origin: str = "http://fastapi:8000"
    read_origin: str = "http://fastapi:8000"
    service_key: str = ""
    direct_reads_enabled: bool = False
    catalog_origin: str = "http://catalog-service:8085"
    cinema_origin: str = "http://cinema-service:8086"
    booking_origin: str = "http://booking-service:8087"
    review_origin: str = "http://review-service:8083"
    writes_enabled: bool = False
    model_url: str = ""
    model_timeout_seconds: float = Field(default=15, gt=0, le=60)
    requests_per_minute: int = Field(default=10, ge=1, le=1000)
    context_ttl_seconds: int = Field(default=1800, ge=60, le=86400)
    model_config = SettingsConfigDict(env_prefix="AI_", extra="ignore", hide_input_in_errors=True)

    @field_validator("read_origin", "identity_origin", "catalog_origin", "cinema_origin", "booking_origin", "review_origin")
    @classmethod
    def origin(cls, value):
        url = httpx.URL(value)
        if url.scheme not in {"http", "https"} or not url.host or url.userinfo or url.path != "/" or url.query or url.fragment:
            raise ValueError("Read/identity URL must be a fixed HTTP(S) origin")
        return str(url).rstrip("/")
