from fastapi import HTTPException, status
from sqlmodel import Session
from app.repositories.film_repo import FilmRepository


class FilmService:

    @staticmethod
    def list_films(db: Session, now_showing: bool = False):
        if now_showing:
            return FilmRepository.get_now_showing(db)
        return FilmRepository.get_all(db)

    @staticmethod
    def get_film_detail(db: Session, film_id: int):
        film = FilmRepository.get_by_id(db, film_id)
        if not film:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Film not found"
            )
        return film
