from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


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


class SentimentDecisionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    content_version: int = Field(gt=0)
    analysis_generation: int = Field(gt=0)
    expected_updated_at: AwareDatetime
    label: Literal["positive", "neutral", "negative"]
    reason: str = Field(min_length=3, max_length=1000)


class SentimentRetryWrite(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
