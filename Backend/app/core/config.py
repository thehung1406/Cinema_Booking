from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    SECRET_KEY: str
    ALGORITHM: str

    DATABASE_URL: str
    POSTGRES_USER : str
    POSTGRES_PASSWORD : str
    POSTGRES_DB : str
    FRONTEND_URL : str
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_URL: str
    TMN_CODE: str
    HASH_SECRET : str
    TMN_CODE : str
    VNPAY_URL : str
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None
    SMTP_TLS: bool = True
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    CORS_ORIGINS: str
settings = Settings()
