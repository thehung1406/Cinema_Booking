from typing import Optional
from sqlmodel import Field, SQLModel


class Genre(SQLModel, table=True):
    __tablename__ = "genres"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, unique=True)


class FilmGenre(SQLModel, table=True):
    __tablename__ = "film_genres"
    film_id: int = Field(primary_key=True, foreign_key="films.id", ondelete="CASCADE")
    genre_id: int = Field(primary_key=True, foreign_key="genres.id", ondelete="RESTRICT")


class FilmFormat(SQLModel, table=True):
    __tablename__ = "film_formats"
    film_id: int = Field(primary_key=True, foreign_key="films.id", ondelete="CASCADE")
    format_id: int = Field(primary_key=True, foreign_key="formats.id", ondelete="RESTRICT")


class Format(SQLModel, table=True):
    __tablename__ = "formats"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(max_length=20, unique=True)
    name: str = Field(max_length=50)
