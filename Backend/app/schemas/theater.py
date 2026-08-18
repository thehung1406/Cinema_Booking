from sqlmodel import SQLModel
from typing import Optional, List


class TheaterRead(SQLModel):
    id: int
    name: str
    address: str
    city: str
    rating: Optional[float] = None
    image: Optional[str] = None
    technologies: List[str] = []
    special: Optional[str] = None