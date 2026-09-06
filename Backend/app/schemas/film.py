from sqlmodel import SQLModel
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

