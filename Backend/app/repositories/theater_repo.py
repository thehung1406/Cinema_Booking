from app.models import Theater, CinemaRoom, Showtime
from sqlmodel import Session, select, and_


class TheaterRepo:
    @staticmethod
    def get_by_id(db: Session, theater_id: int) -> Theater | None:
        return db.get(Theater, theater_id)

    @staticmethod
    def get_all(db: Session) :
        statement = select(Theater)
        return db.exec(statement).all()

    @staticmethod
    def get_theaters_by_film(db: Session, film_id: int):
        stmt = (
            select(Theater)
            .join(CinemaRoom, CinemaRoom.theater_id == Theater.id)
            .join(Showtime, Showtime.room_id == CinemaRoom.id)
            .where(Showtime.film_id == film_id)
            .distinct()
        )
        return db.exec(stmt).all()

    @staticmethod
    def get_by_film(db: Session, film_id: int):
        stmt = (
            select(Theater)
            .join(CinemaRoom, CinemaRoom.theater_id == Theater.id)
            .join(Showtime, Showtime.room_id == CinemaRoom.id)
            .where(
                and_(
                    Showtime.film_id == film_id,
                    Showtime.status == "ACTIVE"
                )
            )
            .distinct()
            .order_by(Theater.name)
        )
        return db.exec(stmt).all()