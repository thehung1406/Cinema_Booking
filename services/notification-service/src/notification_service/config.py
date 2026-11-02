from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    amqp_url: str = ""
    identity_origin: str = "http://fastapi:8000"
    service_key: str = ""
    smtp_host: str = "mailpit"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "cinema@localhost"
    smtp_tls: bool = False
    smtp_timeout_seconds: int = Field(default=10, ge=1, le=30)
    lease_seconds: int = Field(default=300, ge=60, le=1800)
    max_attempts: int = Field(default=5, ge=1, le=20)
    model_config = SettingsConfigDict(env_prefix="NOTIFICATION_", extra="ignore", hide_input_in_errors=True)

    @model_validator(mode="after")
    def validate_smtp(self):
        if bool(self.smtp_user) != bool(self.smtp_password):
            raise ValueError("SMTP user/password must both be configured or both empty")
        if self.lease_seconds < self.smtp_timeout_seconds * 10:
            raise ValueError("Delivery lease must exceed bounded SMTP operations")
        return self
