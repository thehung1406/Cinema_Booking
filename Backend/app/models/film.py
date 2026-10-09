from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import date, datetime
from sqlalchemy import CheckConstraint, Column, DateTime, Text, Index
from .film_classification import FilmGenre, FilmFormat


class Film(SQLModel, table=True):
    __tablename__ = "films"
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="ck_film_duration_positive"),
        Index("ix_films_release_end_date", "release_date", "end_date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    title: str = Field(max_length=100)
    image: Optional[str] = Field(default=None, max_length=255)
    rating: Optional[str] = Field(default=None, max_length=10)

    duration_minutes: Optional[int] = None
    language: Optional[str] = Field(default=None, max_length=50)
    subtitle: Optional[str] = Field(default=None, max_length=50)
    deleted_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))

    release_date: Optional[date] = None
    end_date: Optional[date] = None

    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    trailer: Optional[str] = Field(default=None, max_length=255)

    # Relationships
    showtimes: List["Showtime"] = Relationship(back_populates="film")
    genre_items: List["Genre"] = Relationship(link_model=FilmGenre, sa_relationship_kwargs={"lazy": "selectin", "order_by": "Genre.id"})
    format_items: List["Format"] = Relationship(link_model=FilmFormat, sa_relationship_kwargs={"lazy": "selectin", "order_by": "Format.id"})

    @property
    def genre(self) -> Optional[str]:
        return ", ".join(item.name for item in self.genre_items) or None

    @property
    def formats(self) -> List[str]:
        return [item.name for item in self.format_items]

    @property
    def duration(self) -> Optional[str]:
        return f"{self.duration_minutes} phút" if self.duration_minutes is not None else None
