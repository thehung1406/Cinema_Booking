from sqlmodel import Session, select
from datetime import date
from app.models.film import Film


class FilmRepository:

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 50):
        stmt = select(Film).offset(skip).limit(limit)
        return db.exec(stmt).all()

    @staticmethod
    def get_now_showing(db: Session, skip: int = 0, limit: int = 50):
        today = date.today()
        stmt = select(Film).where(
            Film.release_date <= today,
            Film.end_date >= today
        ).offset(skip).limit(limit)
        return db.exec(stmt).all()

    @staticmethod
    def get_by_id(db: Session, film_id: int):
        return db.get(Film, film_id)

