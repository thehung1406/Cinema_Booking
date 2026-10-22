"""Inputs for the UC01–UC07 administration workflows."""
from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class AdminInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FilmWrite(AdminInput):
    title: str = Field(min_length=1, max_length=100)
    duration_minutes: int = Field(gt=0, le=600)
    release_date: date
    end_date: date
    genre_ids: list[int] = Field(min_length=1, max_length=50)
    format_ids: list[int] = Field(min_length=1, max_length=50)
    image: str | None = Field(default=None, max_length=255)
    rating: str | None = Field(default=None, max_length=10)
    language: str | None = Field(default=None, max_length=50)
    subtitle: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=20000)
    trailer: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def date_range(self):
        if self.end_date < self.release_date:
            raise ValueError("Ngày kết thúc phải từ ngày khởi chiếu trở đi")
        return self


class RoomWrite(AdminInput):
    theater_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=50)
    capacity: int = Field(gt=0, le=2000)
    room_type: str | None = Field(default=None, max_length=50)
    status: Literal["ACTIVE", "MAINTENANCE"] = "ACTIVE"


class SeatWrite(AdminInput):
    seat_type_id: int = Field(gt=0)
    seat_name: str = Field(min_length=1, max_length=10, pattern=r"^[A-Za-z]+[1-9][0-9]*$")

    @field_validator("seat_name")
    @classmethod
    def normalize_name(cls, value):
        return value.upper()


class ShowtimeWrite(AdminInput):
    film_id: int = Field(gt=0)
    room_id: int = Field(gt=0)
    format_id: int = Field(gt=0)
    show_date: date
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def interval(self):
        if self.start_time.tzinfo or self.end_time.tzinfo or self.end_time <= self.start_time:
            raise ValueError("Giờ kết thúc phải sau giờ bắt đầu trong cùng ngày (giờ Việt Nam)")
        return self


class PriceWrite(AdminInput):
    room_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=30)
    base_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class EmployeeWrite(AdminInput):
    full_name: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=100)
    phone: str | None = Field(default=None, max_length=15)


class EmployeeCreate(EmployeeWrite):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=72)
    role_id: int = Field(gt=0)

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Mật khẩu không được vượt quá 72 byte")
        return value


class AccountStatus(AdminInput):
    is_active: bool


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
        from app.services.rag_service import safe_source_url
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


class ReportFilters(AdminInput):
    start_date: date
    end_date: date
    film_id: int | None = Field(default=None, gt=0)
    theater_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def range(self):
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 366:
            raise ValueError("Khoảng báo cáo phải hợp lệ và không quá 367 ngày")
        return self
