from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewWrite(BaseModel):
    content: str = Field(min_length=5, max_length=3000)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value):
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Nội dung cần ít nhất 5 ký tự.")
        return value


class ReviewEdit(ReviewWrite):
    content_version: int = Field(gt=0)


class ModerationWrite(BaseModel):
    content_version: int = Field(gt=0)
    status: Literal["approved", "rejected", "pending"]


class ReviewRead(BaseModel):
    id: int
    content: str
    content_version: int
    moderation_status: str
    updated_at: datetime
    analysis_status: str
    sentiment: str | None = None
    author: str
    is_owner: bool = False
    verified_purchase: bool = False


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


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Literal["search_films", "get_showtimes", "get_ticket_prices", "get_seat_availability", "get_positive_films"]
    context: ToolContext = Field(default_factory=ToolContext)
    query: str = Field(default="", max_length=200)
