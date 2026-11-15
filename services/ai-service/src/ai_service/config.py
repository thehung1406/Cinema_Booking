import httpx
from typing import Literal
from pydantic import Field, SecretStr, field_validator, model_validator
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
    payment_origin: str = "http://payment-service:8088"
    review_origin: str = "http://review-service:8083"
    writes_enabled: bool = False
    model_url: str = ""
    model_timeout_seconds: float = Field(default=15, gt=0, le=60)
    requests_per_minute: int = Field(default=10, ge=1, le=1000)
    context_ttl_seconds: int = Field(default=1800, ge=60, le=86400)
    llm_provider: Literal["disabled", "ollama", "openai"] = "disabled"
    llm_base_url: str = ""
    ollama_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen3:4b"
    llm_keep_alive: str = Field(default="5m", pattern=r"^[1-9][0-9]*(?:s|m|h)$")
    llm_timeout_seconds: float = Field(default=8, gt=0, le=20)
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4.1-mini"
    react_lookup_enabled: bool = True
    retrieval_strategy: Literal["lexical", "bm25", "dense", "hybrid", "rerank"] = "lexical"
    embedding_url: str = ""
    reranker_url: str = ""
    graph_uri: str = ""
    graph_username: str = "neo4j"
    graph_password: SecretStr = SecretStr("")
    graph_database: str = "neo4j"
    graph_release_id: str = Field(default="", pattern=r"^(?:[a-f0-9]{64})?$")
    model_config = SettingsConfigDict(env_prefix="AI_", extra="ignore", hide_input_in_errors=True)

    @model_validator(mode="after")
    def llm_connection(self):
        use_openai = self.llm_provider == "openai"
        if use_openai and not self.openai_api_key.get_secret_value().strip():
            raise ValueError("AI_OPENAI_API_KEY is required when AI_LLM_PROVIDER=openai")
        default_url = "https://api.openai.com/v1" if use_openai else self.ollama_base_url
        url = httpx.URL(self.llm_base_url or default_url)
        if url.scheme not in {"http", "https"} or not url.host or url.userinfo or url.query or url.fragment:
            raise ValueError("AI_LLM_BASE_URL must be an HTTP(S) URL without credentials, query or fragment")
        if use_openai and url.scheme != "https":
            raise ValueError("OpenAI requires HTTPS in AI_LLM_BASE_URL")
        if self.llm_provider == "ollama" and url.path != "/":
            raise ValueError("Ollama requires an origin in AI_LLM_BASE_URL")
        self.llm_base_url = str(url).rstrip("/")
        return self

    @model_validator(mode="after")
    def graph_connection(self):
        if self.graph_uri and not (self.graph_release_id and self.graph_password.get_secret_value()):
            raise ValueError("Graph URI requires a release ID and password")
        return self

    @field_validator("read_origin", "identity_origin", "catalog_origin", "cinema_origin", "booking_origin", "payment_origin", "review_origin", "embedding_url", "reranker_url")
    @classmethod
    def origin(cls, value, info):
        if not value and info.field_name in {"embedding_url", "reranker_url"}:
            return value
        url = httpx.URL(value)
        if url.scheme not in {"http", "https"} or not url.host or url.userinfo or url.path != "/" or url.query or url.fragment:
            raise ValueError("Read/identity URL must be a fixed HTTP(S) origin")
        return str(url).rstrip("/")
