"""Versioned Cinema → Booking contract; no ORM or cross-store connections."""
from datetime import date, time
from decimal import Decimal
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SalesSeat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(gt=0)
    seat_name: str = Field(min_length=1, max_length=10)
    seat_type_id: int = Field(gt=0)
    seat_type: str = Field(min_length=1, max_length=30)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    status: Literal["ACTIVE", "INACTIVE"]


class SalesRoom(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(gt=0)
    theater_id: int = Field(gt=0)
    name: str
    capacity: int = Field(gt=0, le=2000)
    room_type: str | None = None
    status: Literal["ACTIVE", "MAINTENANCE"]


class SalesTheater(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(gt=0)
    name: str
    address: str
    city: str


class SalesSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    showtime_id: int = Field(gt=0)
    sales_version: int = Field(gt=0)
    catalog_binding_id: UUID
    film_id: int = Field(gt=0)
    format_id: int = Field(gt=0)
    film: dict
    room: SalesRoom
    theater: SalesTheater
    show_date: date
    start_time: time
    end_time: time
    status: Literal["ACTIVE", "CANCELLED", "COMPLETED"]
    seat_count: int = Field(ge=0, le=2000)
    seats: list[SalesSeat] = Field(max_length=2000)

    @model_validator(mode="after")
    def complete(self):
        if self.film.get("id") != self.film_id or not self.film.get("catalog_version") or self.format_id not in self.film.get("format_ids", []) or not self.film.get("format_name"):
            raise ValueError("Invalid Catalog publication facts")
        if self.room.theater_id != self.theater.id or len(self.seats) > self.room.capacity or len(self.seats) != self.seat_count:
            raise ValueError("Invalid room/theater capacity")
        if len({s.id for s in self.seats}) != len(self.seats) or len({s.seat_name for s in self.seats}) != len(self.seats):
            raise ValueError("Duplicate published seats")
        if self.start_time.tzinfo or self.end_time.tzinfo or self.end_time <= self.start_time:
            raise ValueError("Invalid published interval")
        return self

    def digest(self):
        data = json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return sha256(data.encode()).hexdigest()


class SalesCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    epoch: int = Field(gt=0)


class ImportSales(SalesCommand):
    snapshot: SalesSnapshot
    digest: str = Field(pattern="^[a-f0-9]{64}$")


class OpenSales(SalesCommand):
    sales_version: int = Field(gt=0)
    digest: str = Field(pattern="^[a-f0-9]{64}$")
