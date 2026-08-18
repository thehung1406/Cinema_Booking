from sqlmodel import Session, select
from datetime import date
from app.models.film import Film


class FilmRepository:

    @staticmethod
    def get_all(db: Session):
        stmt = select(Film)
        return db.exec(stmt).all()

    @staticmethod
    def get_now_showing(db: Session):
        today = date.today()
        stmt = select(Film).where(
            Film.release_date <= today,
            Film.end_date >= today
        )
        return db.exec(stmt).all()

    @staticmethod
    def get_by_id(db: Session, film_id: int):
        return db.get(Film, film_id)
