from sqlmodel import Session, select
from datetime import date
from app.models.film import Film


class FilmRepository:

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 50):
        from app.utils.catalog_ownership import get_owner
        owner = get_owner(db)
        if owner != "monolith":
            from fastapi import HTTPException
            if owner != "service": raise HTTPException(503, "Catalog đang chuyển dữ liệu")
            from app.services.catalog_remote import call, FilmFact
            return [FilmFact.model_validate(f) for f in call("POST", "/internal/v1/films/search", json={"skip": skip, "limit": limit})]
        stmt = select(Film).where(Film.deleted_at.is_(None)).offset(skip).limit(limit)
        return db.exec(stmt).all()

    @staticmethod
    def get_now_showing(db: Session, skip: int = 0, limit: int = 50):
        from app.utils.catalog_ownership import get_owner
        owner = get_owner(db)
        if owner != "monolith":
            from fastapi import HTTPException
            if owner != "service": raise HTTPException(503, "Catalog đang chuyển dữ liệu")
            from app.services.catalog_remote import call, FilmFact
            return [FilmFact.model_validate(f) for f in call("POST", "/internal/v1/films/search", json={"skip": skip, "limit": limit, "now_showing": True})]
        today = date.today()
        stmt = select(Film).where(
            Film.deleted_at.is_(None),
            Film.release_date <= today,
            Film.end_date >= today
        ).offset(skip).limit(limit)
        return db.exec(stmt).all()

    @staticmethod
    def get_by_id(db: Session, film_id: int):
        from app.services.catalog_remote import get_film
        return get_film(db, film_id)

