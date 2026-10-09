from sqlmodel import Session, select, and_
from datetime import date
from app.models.showtime import Showtime, ShowtimeStatus
from app.models.cinema_room import CinemaRoom
from app.models import Film, Theater


class ShowtimeRepository:

    @staticmethod
    def get_by_id(db: Session, showtime_id: int):
        """Lấy showtime theo ID"""
        return db.exec(select(Showtime).join(Film).join(CinemaRoom).join(Theater)
            .where(Showtime.id == showtime_id, Film.deleted_at.is_(None),
                   CinemaRoom.deleted_at.is_(None), Theater.deleted_at.is_(None),
                   Showtime.status == ShowtimeStatus.ACTIVE, CinemaRoom.status == "ACTIVE")).first()

    @staticmethod
    def get_showtime_by_id(db: Session, showtime_id: int):
        """Alias dùng bởi seat/booking services."""
        return ShowtimeRepository.get_by_id(db, showtime_id)

    @staticmethod
    def get_showtimes_by_film_theater_date(
            db: Session,
            film_id: int,
            theater_id: int,
            show_date: date,
    ):
        stmt = (
            select(Showtime)
            .join(CinemaRoom, CinemaRoom.id == Showtime.room_id)
            .join(Film, Film.id == Showtime.film_id)
            .join(Theater, Theater.id == CinemaRoom.theater_id)
            .where(
                and_(
                    Showtime.film_id == film_id,
                    Film.deleted_at.is_(None), Theater.deleted_at.is_(None),
                    CinemaRoom.deleted_at.is_(None), CinemaRoom.status == "ACTIVE",
                    CinemaRoom.theater_id == theater_id,
                    Showtime.show_date == show_date,
                    Showtime.status == ShowtimeStatus.ACTIVE,
                )
            )
            .order_by(Showtime.start_time)
        )
        return db.exec(stmt).all()
