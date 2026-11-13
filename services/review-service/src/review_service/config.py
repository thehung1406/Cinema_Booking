import httpx
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    identity_origin: str = "http://fastapi:8000"
    read_origin: str = "http://fastapi:8000"
    service_key: str = ""
    direct_reads_enabled: bool = False
    catalog_origin: str = "http://catalog-service:8085"
    booking_origin: str = "http://booking-service:8087"
    writes_enabled: bool = False
    auto_approve: bool = False
    sentiment_backend: str = "disabled"
    sentiment_model_path: str = "/models/sentiment"
    sentiment_demo_lr_path: str = ""
    sentiment_demo_visobert_path: str = ""
    sentiment_review_threshold: float = Field(default=0.65, ge=0, le=1)
    sentiment_window_days: int = Field(default=30, ge=1, le=365)
    sentiment_min_reviews: int = Field(default=10, ge=1)
    max_attempts: int = Field(default=5, ge=1, le=20)
    retry_seconds: int = Field(default=60, ge=1, le=3600)
    amqp_public_url: str = ""
    model_config = SettingsConfigDict(env_prefix="REVIEW_", extra="ignore", hide_input_in_errors=True)

    @field_validator("read_origin", "identity_origin", "catalog_origin", "booking_origin")
    @classmethod
    def origin(cls, value):
        url = httpx.URL(value)
        if url.scheme not in {"http", "https"} or not url.host or url.userinfo or url.path != "/" or url.query or url.fragment:
            raise ValueError("Read/identity URL must be a fixed HTTP(S) origin")
        return str(url).rstrip("/")
