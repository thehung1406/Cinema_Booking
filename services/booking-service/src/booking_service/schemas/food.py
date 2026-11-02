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
