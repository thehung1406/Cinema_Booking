from sqlmodel import SQLModel
from typing import Optional,List
from datetime import date


class FilmRead(SQLModel):
    id: int
    title: str
    image: Optional[str]
    rating: Optional[str]
    duration: Optional[str]
    genre: Optional[str]


class FilmDetailRead(FilmRead):
    language: Optional[str]
    subtitle: Optional[str]
    formats:    Optional[List[str]]
    release_date: Optional[date]
    end_date: Optional[date]
    description: Optional[str]
    trailer: Optional[str]
