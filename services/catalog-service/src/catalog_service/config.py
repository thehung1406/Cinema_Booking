import httpx
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    identity_origin: str = "http://identity-service:8084"
    read_origin: str = "http://fastapi:8000"
    service_key: str = ""
    writes_enabled: bool = False
    quote_seconds: int = Field(default=120, ge=30, le=600)
    model_config = SettingsConfigDict(env_prefix="CATALOG_", extra="ignore", hide_input_in_errors=True)

    @field_validator("identity_origin", "read_origin")
    @classmethod
    def origin(cls, value):
        url = httpx.URL(value)
        if url.scheme not in {"http", "https"} or not url.host or url.userinfo or url.path != "/" or url.query or url.fragment:
            raise ValueError("Catalog origins must be fixed HTTP(S) origins")
        return str(url).rstrip("/")
