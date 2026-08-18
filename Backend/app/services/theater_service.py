from sqlmodel import Session
from app.repositories.theater_repo import TheaterRepo

class TheaterService:
    @staticmethod
    def get_all_theaters(db: Session):
        return TheaterRepo.get_all(db)

    @staticmethod
    def get_theater_by_id(db: Session, theater_id: int):
        return TheaterRepo.get_by_id(db, theater_id)


    @staticmethod
    def get_theaters_by_film(db: Session, film_id: int):
        return TheaterRepo.get_by_film(db, film_id)