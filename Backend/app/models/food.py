from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Column, JSON, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


class FoodItem(SQLModel, table=True):
    __tablename__ = "food_items"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_food_price"),
        CheckConstraint("category IN ('POPCORN', 'DRINK', 'COMBO')", name="ck_food_category"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=150)
    description: str = Field(default="", max_length=500)
    category: str = Field(max_length=20)
    price: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    is_active: bool = Field(default=True)


class ComboItem(SQLModel, table=True):
    __tablename__ = "combo_items"
    __table_args__ = (
        UniqueConstraint("combo_id", "food_item_id", name="uq_combo_component"),
        CheckConstraint("quantity > 0", name="ck_combo_quantity"),
        CheckConstraint("combo_id <> food_item_id", name="ck_combo_not_self"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    combo_id: int = Field(foreign_key="food_items.id", ondelete="RESTRICT", index=True)
    food_item_id: int = Field(foreign_key="food_items.id", ondelete="RESTRICT", index=True)
    quantity: int


class BookingFoodItem(SQLModel, table=True):
    __tablename__ = "booking_food_items"
    __table_args__ = (
        UniqueConstraint("booking_id", "food_item_id", name="uq_booking_food"),
        CheckConstraint("quantity BETWEEN 1 AND 20", name="ck_booking_food_quantity"),
        CheckConstraint("unit_price > 0", name="ck_booking_food_price"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    booking_id: int = Field(foreign_key="bookings.id", ondelete="RESTRICT", index=True)
    food_item_id: int = Field(foreign_key="food_items.id", ondelete="RESTRICT", index=True)
    name: str = Field(max_length=150)
    category: str = Field(max_length=20)
    quantity: int
    unit_price: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    components: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
