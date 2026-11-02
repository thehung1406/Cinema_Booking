from sqlmodel import Session, select
from app.models.cinema_room import CinemaRoom

class CinemaRoomRepository:
    @staticmethod
    def get_by_id(db: Session, room_id: int) -> CinemaRoom | None:
        from app.utils.cinema_ownership import get_owner
        if get_owner(db)=="service":
            from app.services.cinema_remote import object_at
            return object_at(f"/cinema-rooms/{room_id}")
        return db.exec(select(CinemaRoom).where(CinemaRoom.id == room_id, CinemaRoom.deleted_at.is_(None))).first()

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 50):
        from app.utils.cinema_ownership import get_owner
        if get_owner(db)=="service":
            from app.services.cinema_remote import call
            from types import SimpleNamespace
            return [SimpleNamespace(**r) for r in call("GET","/cinema-rooms/",params={"skip":skip,"limit":limit})]
        statement = select(CinemaRoom).where(CinemaRoom.deleted_at.is_(None)).offset(skip).limit(limit)
        return db.exec(statement).all()

    @staticmethod
    def get_by_theater(db: Session, theater_id: int, skip: int = 0, limit: int = 50):
        from app.utils.cinema_ownership import get_owner
        if get_owner(db)=="service":
            from app.services.cinema_remote import call
            from types import SimpleNamespace
            return [SimpleNamespace(**r) for r in call("GET","/cinema-rooms/",params={"theater_id":theater_id,"skip":skip,"limit":limit})]
        statement = select(CinemaRoom).where(CinemaRoom.theater_id == theater_id, CinemaRoom.deleted_at.is_(None)).offset(skip).limit(limit)
        return db.exec(statement).all()
