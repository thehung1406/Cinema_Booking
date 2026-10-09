from app.models import Theater, CinemaRoom, Showtime
from sqlmodel import Session, select, and_
from datetime import date
from typing import Optional


class TheaterRepo:
    @staticmethod
    def get_by_id(db: Session, theater_id: int) -> Theater | None:
        return db.exec(select(Theater).where(Theater.id == theater_id, Theater.deleted_at.is_(None))).first()

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 50):
        statement = select(Theater).where(Theater.deleted_at.is_(None)).offset(skip).limit(limit)
        return db.exec(statement).all()

    @staticmethod
    def get_by_film(db: Session, film_id: int, from_date: Optional[date] = None):
        if from_date is None:
            from_date = date.today()
        stmt = (
            select(Theater)
            .join(CinemaRoom, CinemaRoom.theater_id == Theater.id)
            .join(Showtime, Showtime.room_id == CinemaRoom.id)
            .where(
                and_(
                    Showtime.film_id == film_id,
                    Theater.deleted_at.is_(None),
                    CinemaRoom.deleted_at.is_(None),
                    CinemaRoom.status == "ACTIVE",
                    Showtime.status == "ACTIVE",
                    Showtime.show_date >= from_date,
                )
            )
            .distinct()
            .order_by(Theater.name)
        )
        return db.exec(stmt).all()
