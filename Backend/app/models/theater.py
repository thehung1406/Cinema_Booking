from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Dict, List
from decimal import Decimal
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Numeric as SaNumeric

class Theater(SQLModel, table=True):
    __tablename__ = "theaters"

    id: Optional[int] = Field(default=None, primary_key=True)

    name: str = Field(max_length=100)
    address: str = Field(max_length=255)
    city: str = Field(max_length=50)

    image: Optional[str] = Field(default=None, max_length=255)
    rating: Optional[Decimal] = Field(default=None, sa_column=Column(SaNumeric(3, 1), nullable=True))

    technologies: Optional[Dict] = Field(
        default=None,
        sa_column=Column(JSONB)
    )
    special: Optional[str] = Field(default=None, max_length=50)

    # Relationships
    cinema_rooms: List["CinemaRoom"] = Relationship(back_populates="theater")

