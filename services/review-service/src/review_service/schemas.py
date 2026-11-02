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
