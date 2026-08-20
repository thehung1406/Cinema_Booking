from datetime import date
from typing import Optional
from sqlmodel import Session
from app.repositories.theater_repo import TheaterRepo

class TheaterService:
    @staticmethod
    def get_all_theaters(db: Session, skip: int = 0, limit: int = 50):
        return TheaterRepo.get_all(db, skip=skip, limit=limit)

    @staticmethod
    def get_theater_by_id(db: Session, theater_id: int):
        return TheaterRepo.get_by_id(db, theater_id)

    @staticmethod
    def get_theaters_by_film(db: Session, film_id: int, from_date: Optional[date] = None):
        return TheaterRepo.get_by_film(db, film_id, from_date)