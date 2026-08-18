from sqlmodel import Session, select
from datetime import date
from fastapi import HTTPException, status
from app.repositories.showtime_repo import ShowtimeRepository
from app.models.showtime import Showtime
from app.models.film import Film
from app.models.cinema_room import CinemaRoom
from app.models.theater import Theater

class ShowtimeService:

    @staticmethod
    def get_showtimes(
        db: Session,
        film_id: int,
        theater_id: int,
        show_date: date,
    ):
        return ShowtimeRepository.get_showtimes_by_film_theater_date(
            db=db,
            film_id=film_id,
            theater_id=theater_id,
            show_date=show_date,)
    
    @staticmethod
    def get_showtime_by_id(db: Session, showtime_id: int):
        # Single JOIN query thay vì 4 query riêng biệt
        stmt = (
            select(Showtime, Film, CinemaRoom, Theater)
            .join(Film, Film.id == Showtime.film_id)
            .join(CinemaRoom, CinemaRoom.id == Showtime.room_id)
            .join(Theater, Theater.id == CinemaRoom.theater_id)
            .where(Showtime.id == showtime_id)
        )
        result = db.exec(stmt).first()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy suất chiếu"
            )

        showtime, film, room, theater = result

        # Trả về đầy đủ thông tin
        return {
            "id": showtime.id,
            "show_date": showtime.show_date,
            "start_time": showtime.start_time,
            "end_time": showtime.end_time,
            "format": showtime.format,
            "status": showtime.status,
            
            # Thông tin phim
            "film_id": film.id,
            "film_title": film.title,
            "image": film.image,
            "duration": film.duration,
            "language": film.language,
            "subtitle": film.subtitle,
            
            # Thông tin phòng và rạp
            "room_id": room.id,
            "room_name": room.name,
            "theater_id": theater.id,
            "theater_name": theater.name,
            "theater_address": theater.address,
        }