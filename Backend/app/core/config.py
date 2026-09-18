import json
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    SECRET_KEY: str
    ALGORITHM: str

    DATABASE_URL: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    FRONTEND_URL: str
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_URL: str
    TMN_CODE: str
    HASH_SECRET: str
    VNPAY_URL: str
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None
    SMTP_TLS: bool = True
    # Disabled inference remains retryable until a reviewed artifact is installed.
    SENTIMENT_BACKEND: str = "disabled"  # disabled | sklearn | transformers
    SENTIMENT_MODEL_PATH: str = "artifacts/sentiment"
    SENTIMENT_REVIEW_THRESHOLD: float = Field(default=0.65, ge=0, le=1)
    REVIEW_AUTO_APPROVE: bool = False
    SENTIMENT_WINDOW_DAYS: int = Field(default=30, ge=1, le=365)
    SENTIMENT_MIN_REVIEWS: int = Field(default=10, ge=1)
    AI_MODEL_URL: str = ""  # private inference service, e.g. http://ai-model:8010
    AI_MODEL_TIMEOUT_SECONDS: float = Field(default=15.0, gt=0, le=60)
    AI_REQUESTS_PER_MINUTE: int = Field(default=10, ge=1, le=1000)
    AI_CONTEXT_TTL_SECONDS: int = Field(default=1800, ge=60, le=86400)

    CORS_ORIGINS: List[str] = []

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Accept JSON array string or comma-separated string."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return []

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

