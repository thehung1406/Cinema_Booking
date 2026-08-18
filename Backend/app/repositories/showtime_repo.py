from sqlmodel import Session, select, and_
from datetime import date
from app.models.showtime import Showtime
from app.models.cinema_room import CinemaRoom


class ShowtimeRepository:

    @staticmethod
    def get_by_id(db: Session, showtime_id: int):
        """Lấy showtime theo ID"""
        return db.get(Showtime, showtime_id)

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
            .where(
                and_(
                    Showtime.film_id == film_id,
                    CinemaRoom.theater_id == theater_id,
                    Showtime.show_date == show_date,
                    Showtime.status == "ACTIVE",
                )
            )
            .order_by(Showtime.start_time)
        )
        return db.exec(stmt).all()
    
    @staticmethod
    def get_showtime_by_id(db: Session, showtime_id: int):
        """Lấy chi tiết showtime theo ID"""
        return db.get(Showtime, showtime_id)
