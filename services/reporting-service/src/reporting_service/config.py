import httpx
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SOURCES = ("booking", "payment", "catalog", "cinema", "review")


class Settings(BaseSettings):
    database_url: str
    identity_origin: str = "http://identity-service:8084"
    service_key: str = ""
    writes_enabled: bool = False
    amqp_url: str = ""
    stale_seconds: int = Field(default=60, ge=10, le=3600)
    source_origins: dict[str, str] = Field(
        default_factory=lambda: {
            "booking": "http://booking-service:8087",
            "payment": "http://payment-service:8088",
            "catalog": "http://catalog-service:8085",
            "cinema": "http://cinema-service:8086",
            "review": "http://review-service:8083",
        }
    )
    model_config = SettingsConfigDict(
        env_prefix="REPORTING_", extra="ignore", hide_input_in_errors=True
    )

    @field_validator("source_origins")
    @classmethod
    def origins(cls, value):
        if set(value) != set(SOURCES):
            raise ValueError("Every reporting owner is required")
        for origin in value.values():
            url = httpx.URL(origin)
            if (
                url.scheme not in {"http", "https"}
                or not url.host
                or url.userinfo
                or url.path != "/"
                or url.query
                or url.fragment
            ):
                raise ValueError("Fixed HTTP origins required")
        return {k: v.rstrip("/") for k, v in value.items()}
