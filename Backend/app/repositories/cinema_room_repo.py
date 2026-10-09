from sqlmodel import Session, select
from app.models.cinema_room import CinemaRoom

class CinemaRoomRepository:
    @staticmethod
    def get_by_id(db: Session, room_id: int) -> CinemaRoom | None:
        return db.exec(select(CinemaRoom).where(CinemaRoom.id == room_id, CinemaRoom.deleted_at.is_(None))).first()

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 50):
        statement = select(CinemaRoom).where(CinemaRoom.deleted_at.is_(None)).offset(skip).limit(limit)
        return db.exec(statement).all()

    @staticmethod
    def get_by_theater(db: Session, theater_id: int, skip: int = 0, limit: int = 50):
        statement = select(CinemaRoom).where(CinemaRoom.theater_id == theater_id, CinemaRoom.deleted_at.is_(None)).offset(skip).limit(limit)
        return db.exec(statement).all()
