from sqlmodel import SQLModel
from typing import Optional


class TheaterRead(SQLModel):
    id: int
    name: str
    address: str
    city: str
    rating: Optional[float] = None
    image: Optional[str] = None
    technologies: Optional[dict] = None
    special: Optional[str] = None
