from datetime import date, time
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class AdminInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class RoomWrite(AdminInput):
    theater_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=50)
    capacity: int = Field(gt=0, le=2000)
    room_type: str | None = Field(default=None, max_length=50)
    status: Literal["ACTIVE", "MAINTENANCE"] = "ACTIVE"


class SeatWrite(AdminInput):
    status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"
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
