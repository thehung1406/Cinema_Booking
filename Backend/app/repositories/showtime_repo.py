from sqlmodel import Session, select, and_
from datetime import date
from app.models.showtime import Showtime, ShowtimeStatus
from app.models.cinema_room import CinemaRoom
from app.models import Film, Theater


class ShowtimeRepository:

    @staticmethod
    def get_by_id(db: Session, showtime_id: int):
        """Lấy showtime theo ID"""
        from app.utils.cinema_ownership import get_owner as cinema_owner
        if cinema_owner(db) == "service":
            from app.services.sales_service import configuration
            from fastapi import HTTPException
            try:
                item = configuration(db, showtime_id)
            except HTTPException as exc:
                if exc.status_code == 409: return None
                raise
            return item if item.status == "ACTIVE" else None
        from app.utils.catalog_ownership import get_owner
        owner = get_owner(db)
        if owner == "maintenance":
            from fastapi import HTTPException
            raise HTTPException(503, "Catalog đang chuyển dữ liệu")
        stmt = select(Showtime).join(CinemaRoom).join(Theater)
        if owner == "monolith":
            stmt = stmt.join(Film, Film.id == Showtime.film_id).where(Film.deleted_at.is_(None))
        return db.exec(stmt.where(Showtime.id == showtime_id,
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
        from app.utils.cinema_ownership import get_owner as cinema_owner
        if cinema_owner(db)=="service":
            from app.services.cinema_remote import call
            from types import SimpleNamespace
            return [SimpleNamespace(**r) for r in call("GET","/showtimes",params={"film_id":film_id,"theater_id":theater_id,"date":show_date.isoformat()})]
        stmt = (
            select(Showtime)
            .join(CinemaRoom, CinemaRoom.id == Showtime.room_id)
            .join(Theater, Theater.id == CinemaRoom.theater_id)
            .where(
                and_(
                    Showtime.film_id == film_id,
                    Theater.deleted_at.is_(None),
                    CinemaRoom.deleted_at.is_(None), CinemaRoom.status == "ACTIVE",
                    CinemaRoom.theater_id == theater_id,
                    Showtime.show_date == show_date,
                    Showtime.status == ShowtimeStatus.ACTIVE,
                )
            )
            .order_by(Showtime.start_time)
        )
        from app.utils.catalog_ownership import get_owner
        owner = get_owner(db)
        if owner == "monolith":
            stmt = stmt.join(Film, Film.id == Showtime.film_id).where(Film.deleted_at.is_(None))
        elif owner == "maintenance":
            from fastapi import HTTPException
            raise HTTPException(503, "Catalog đang chuyển dữ liệu")
        return db.exec(stmt).all()
