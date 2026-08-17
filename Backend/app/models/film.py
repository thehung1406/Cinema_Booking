from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Dict, List
from datetime import date
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB


class Film(SQLModel, table=True):
    __tablename__ = "films"

    id: Optional[int] = Field(default=None, primary_key=True)

    title: str = Field(max_length=100)
    image: Optional[str] = Field(default=None, max_length=255)
    rating: Optional[str] = Field(default=None, max_length=10)

    duration: Optional[str] = Field(default=None, max_length=20)
    genre: Optional[str] = Field(default=None, max_length=100)
    language: Optional[str] = Field(default=None, max_length=50)
    subtitle: Optional[str] = Field(default=None, max_length=50)
    formats: Optional[Dict] = Field(
        default=None,
        sa_column=Column(JSONB)
    )

    release_date: Optional[date] = None
    end_date: Optional[date] = None

    description: Optional[str] = None
    trailer: Optional[str] = Field(default=None, max_length=255)

    # Relationships
    showtimes: List["Showtime"] = Relationship(back_populates="film")
