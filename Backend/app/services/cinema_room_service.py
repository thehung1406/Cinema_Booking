from sqlmodel import Session
from app.repositories.cinema_room_repo import CinemaRoomRepository

class CinemaRoomService:
    @staticmethod
    def get_room_by_id(db: Session, room_id: int):
        return CinemaRoomRepository.get_by_id(db, room_id)

    @staticmethod
    def get_all_rooms(db: Session, skip: int = 0, limit: int = 50):
        return CinemaRoomRepository.get_all(db, skip=skip, limit=limit)

    @staticmethod
    def get_rooms_by_theater(db: Session, theater_id: int, skip: int = 0, limit: int = 50):
        return CinemaRoomRepository.get_by_theater(db, theater_id, skip=skip, limit=limit)
