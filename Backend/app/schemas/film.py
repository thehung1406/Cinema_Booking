from sqlmodel import SQLModel
from typing import Optional, List
from datetime import date


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
    formats: Optional[List[str]]
    description: Optional[str]
    trailer: Optional[str]
