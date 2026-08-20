from sqlmodel import Session, select
from app.models.cinema_room import CinemaRoom

class CinemaRoomRepository:
    @staticmethod
    def get_by_id(db: Session, room_id: int) -> CinemaRoom | None:
        return db.get(CinemaRoom, room_id)

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 50):
        statement = select(CinemaRoom).offset(skip).limit(limit)
        return db.exec(statement).all()

    @staticmethod
    def get_by_theater(db: Session, theater_id: int, skip: int = 0, limit: int = 50):
        statement = select(CinemaRoom).where(CinemaRoom.theater_id == theater_id).offset(skip).limit(limit)
        return db.exec(statement).all()
