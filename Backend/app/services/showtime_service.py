from sqlmodel import Session
from datetime import date
from fastapi import HTTPException, status
from app.repositories.showtime_repo import ShowtimeRepository
from app.repositories.film_repo import FilmRepository
from app.repositories.cinema_room_repo import CinemaRoomRepository
from app.repositories.theater_repo import TheaterRepo

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
        showtime = ShowtimeRepository.get_showtime_by_id(db=db, showtime_id=showtime_id)
        if not showtime:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy suất chiếu"
            )
        
        # Lấy thông tin phim
        film = FilmRepository.get_by_id(db=db, film_id=showtime.film_id)
        if not film:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy thông tin phim"
            )
        
        # Lấy thông tin phòng chiếu
        room = CinemaRoomRepository.get_by_id(db=db, room_id=showtime.room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy thông tin phòng chiếu"
            )
        
        # Lấy thông tin rạp
        theater = TheaterRepo.get_by_id(db=db, theater_id=room.theater_id)
        if not theater:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy thông tin rạp"
            )
        
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