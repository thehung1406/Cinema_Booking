from sqlmodel import Session, select
from app.models.cinema_room import CinemaRoom

class CinemaRoomRepository:
    @staticmethod
    def get_by_id(db: Session, room_id: int):
        return db.get(CinemaRoom, room_id)

    @staticmethod
    def get_by_theater(db: Session, theater_id: int):
        statement = select(CinemaRoom).where(CinemaRoom.theater_id == theater_id)
        return db.exec(statement).all()

