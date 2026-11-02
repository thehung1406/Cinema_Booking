from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

class ToolContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    film_id: int | None = Field(default=None, gt=0)
    theater_id: int | None = Field(default=None, gt=0)
    show_date: date | None = None
    showtime_id: int | None = Field(default=None, gt=0)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    context: ToolContext = Field(default_factory=ToolContext)

    @field_validator("message")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Câu hỏi không được để trống")
        return value.strip()


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageRead(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    metadata: dict
    created_at: datetime


class ConversationDetail(ConversationRead):
    context: ToolContext
    messages: list[MessageRead]
    next_before_id: int | None = None


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Literal["search_films", "get_showtimes", "get_ticket_prices", "get_seat_availability", "get_positive_films"]
    context: ToolContext = Field(default_factory=ToolContext)
    query: str = Field(default="", max_length=200)
class AdminInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DocumentWrite(AdminInput):
    source_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=50)
    source_url: str = Field(min_length=1, max_length=500)
    effective_at: datetime
    content: str = Field(min_length=1, max_length=200000)
    # Required on replacement; returned by the review screen. Never approve stale content.
    expected_updated_at: datetime | None = None

    @field_validator("source_url")
    @classmethod
    def source(cls, value):
        from .rag import safe_source_url
        return safe_source_url(value)

    @field_validator("effective_at", "expected_updated_at")
    @classmethod
    def aware_date(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Thời điểm phải có múi giờ")
        return value


class DocumentApproval(AdminInput):
    version: str = Field(min_length=1, max_length=50)
    expected_updated_at: datetime
    approved: bool = True
