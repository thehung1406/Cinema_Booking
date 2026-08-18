from typing import List, Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.core.database import get_session
from app.schemas.theater import TheaterRead
from app.services.theater_service import TheaterService

router = APIRouter(prefix="/theater", tags=["Theater"])


@router.get("/", response_model=List[TheaterRead])
def get_theaters(db: Session = Depends(get_session)):
    return TheaterService.get_all_theaters(db)


@router.get("/{theater_id}", response_model=TheaterRead)
def get_theater(theater_id: int, db: Session = Depends(get_session)):
    theater = TheaterService.get_theater_by_id(db, theater_id)
    if not theater:
        raise HTTPException(status_code=404, detail="Theater not found")
    return theater


@router.get("/by-film/{film_id}", response_model=List[TheaterRead])
def get_theaters_by_film(
    film_id: int,
    from_date: Optional[date] = Query(default=None, description="Lọc các rạp có suất chiếu từ ngày này"),
    db: Session = Depends(get_session),
):
    return TheaterService.get_theaters_by_film(db, film_id, from_date)
