"""Read-only discovery of currently sellable configurations, never reservations."""
from datetime import date, time
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class BookingOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    show_date: date
    film_id: int | None = Field(default=None, gt=0)
    theater_id: int | None = Field(default=None, gt=0)
    film_name: str = Field(default="", max_length=200)
    theater_name: str = Field(default="", max_length=200)
    genre: str = Field(default="", max_length=100)
    language: str = Field(default="", max_length=100)
    city: str = Field(default="", max_length=100)
    format: str = Field(default="", max_length=50)
    start_after: time | None = None
    start_before: time | None = None
    duration_max: int | None = Field(default=None, ge=1, le=600)
    party_size: int = Field(default=1, ge=1, le=20)
    budget_total: Decimal | None = Field(default=None, gt=0, le=100000000)
    budget_per_ticket: Decimal | None = Field(default=None, gt=0, le=100000000)
    offset: int = Field(default=0, ge=0, le=10000)
    limit: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def interval(self):
        for value in (self.start_after, self.start_before):
            if value is not None and value.tzinfo is not None:
                raise ValueError("Times must use local cinema time without timezone")
        if self.start_after and self.start_before and self.start_after > self.start_before:
            raise ValueError("Invalid time interval")
        return self
