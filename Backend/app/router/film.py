from fastapi import APIRouter, Depends, Query
from typing import List
from sqlmodel import Session

from app.core.database import get_session
from app.schemas.film import FilmRead, FilmDetailRead
from app.services.film_service import FilmService

router = APIRouter(
    prefix="/films",
    tags=["Films"]
)


@router.get("/", response_model=List[FilmRead])
def list_films(
    now_showing: bool = Query(default=False),
    skip: int = Query(default=0, ge=0, description="Số bản ghi bỏ qua"),
    limit: int = Query(default=50, ge=1, le=200, description="Số bản ghi tối đa"),
    db: Session = Depends(get_session),
):
    return FilmService.list_films(db, now_showing, skip=skip, limit=limit)


@router.get("/{film_id}", response_model=FilmDetailRead)
def get_film_detail(
    film_id: int,
    db: Session = Depends(get_session),
):
    return FilmService.get_film_detail(db, film_id)
