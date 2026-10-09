from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)

    username: str = Field(max_length=50, unique=True, index=True)
    password: str = Field(max_length=100)
    email: str = Field(max_length=100, unique=True, index=True)

    phone: Optional[str] = Field(default=None, max_length=15)
    full_name: Optional[str] = Field(default=None, max_length=100)
    avatar: Optional[str] = Field(default=None, max_length=255)

    role_id: int = Field(foreign_key="roles.id", ondelete="RESTRICT", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))

    # Relationships
    bookings: List["Booking"] = Relationship(back_populates="user")
    seat_statuses: List["SeatStatus"] = Relationship(back_populates="hold_user")
    role_item: "Role" = Relationship(sa_relationship_kwargs={"lazy": "joined"})

    @property
    def role(self) -> str:
        return self.role_item.code

