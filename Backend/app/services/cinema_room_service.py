from sqlmodel import Session
from app.repositories.cinema_room_repo import CinemaRoomRepository

class CinemaRoomService:
    @staticmethod
    def get_rooms_by_theater(db: Session, theater_id: int):
        return CinemaRoomRepository.get_by_theater(db, theater_id)
