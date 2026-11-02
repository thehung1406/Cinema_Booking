from datetime import date, time
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal
from uuid import UUID

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



from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FoodSelection(BaseModel):
    food_item_id: int = Field(gt=0, strict=True)
    quantity: int = Field(ge=1, le=20, strict=True)


class FoodComponent(BaseModel):
    food_item_id: int
    name: str
    quantity: int


class FoodItemRead(BaseModel):
    id: int
    name: str
    description: str
    category: Literal["POPCORN", "DRINK", "COMBO"]
    price: Decimal
    components: list[FoodComponent] = Field(default_factory=list)


class BookingFoodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    food_item_id: int
    name: str
    category: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    components: list[FoodComponent] = Field(default_factory=list)


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selections: list[FoodSelection] = Field(max_length=50)

class FilmIds(BaseModel):
    ids: list[int] = Field(max_length=200)
    include_retired: bool = False


class FilmSearch(BaseModel):
    q: str = Field(default="", max_length=2000)
    limit: int = Field(default=8, ge=1, le=200)
    skip: int = Field(default=0, ge=0)
    now_showing: bool = False


class FilmMatch(BaseModel):
    message: str = Field(max_length=2000)


class BindingReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference: str = Field(pattern=r"^cinema-(?:showtime:[1-9][0-9]*|operation:[a-f0-9-]{36})$", max_length=100)

class BindingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    film_id: int = Field(gt=0)
    format_id: int = Field(gt=0)
    show_date: date
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def interval(self):
        if self.start_time.tzinfo or self.end_time.tzinfo or self.end_time <= self.start_time:
            raise ValueError("Invalid schedule interval")
        return self


class ComponentWrite(BaseModel):
    food_item_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=100)


class FoodWrite(AdminInput):
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=500)
    category: Literal["POPCORN", "DRINK", "COMBO"]
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    is_active: bool = True
    components: list[ComponentWrite] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def components_valid(self):
        if (self.category == "COMBO") != bool(self.components):
            raise ValueError("Only a combo has a nonempty component list")
        if len({p.food_item_id for p in self.components}) != len(self.components):
            raise ValueError("Duplicate combo component")
        return self

from pydantic import BaseModel as SQLModel
from typing import Optional, List, Any
from datetime import date
from pydantic import field_validator


class FilmRead(SQLModel):
    id: int
    title: str
    image: Optional[str]
    rating: Optional[str]
    duration: Optional[str]
    genre: Optional[str]
    language: Optional[str]
    subtitle: Optional[str]
    release_date: Optional[date]
    end_date: Optional[date]


class FilmDetailRead(FilmRead):
    formats: Optional[List[str]] = None
    description: Optional[str] = None
    trailer: Optional[str] = None

    @field_validator("formats", mode="before")
    @classmethod
    def parse_formats(cls, v: Any) -> Optional[List[str]]:
        if v is None:
            return None
        if isinstance(v, dict):
            # Nếu dạng {"2D": true, "IMAX": true}, lấy các keys có value True hoặc toàn bộ keys
            active_keys = [k for k, val in v.items() if val]
            return active_keys if active_keys else list(v.keys())
        if isinstance(v, list):
            return [str(item) for item in v]
        if isinstance(v, str):
            return [v]
        return []
