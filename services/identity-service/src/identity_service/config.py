from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./identity.db"
    service_key: str = ""
    writes_enabled: bool = False
    issuer: str = "cinema-identity"
    audience: str = "cinema-api"
    current_kid: str = ""
    signing_keys: dict[str, str] = Field(default_factory=dict, repr=False)
    access_minutes: int = Field(default=15, ge=1, le=60)
    refresh_days: int = Field(default=7, ge=1, le=30)
    read_origin: str = "http://fastapi:8000"
    model_config = SettingsConfigDict(env_prefix="IDENTITY_", extra="ignore", hide_input_in_errors=True)

    @model_validator(mode="after")
    def keys(self):
        if self.writes_enabled and (self.current_kid not in self.signing_keys or
                any(len(key.encode()) < 32 for key in self.signing_keys.values())):
            raise ValueError("Identity needs a current signing key and keys of at least 32 bytes")
        return self
