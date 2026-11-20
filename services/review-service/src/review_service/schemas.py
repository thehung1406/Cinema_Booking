from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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


class ReviewRead(BaseModel):
    id: int
    content: str
    content_version: int
    moderation_status: str
    updated_at: datetime
    analysis_status: str
    sentiment: str | None = None
    author: str
    author_avatar: str | None = None
    is_owner: bool = False
    verified_purchase: bool = False


class AdminReviewRead(ReviewRead):
    film_id: int
    scores: dict[str, float]
    model_version: str | None


class AdminReviewList(BaseModel):
    items: list[AdminReviewRead]
    total: int


class SentimentRetryWrite(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
