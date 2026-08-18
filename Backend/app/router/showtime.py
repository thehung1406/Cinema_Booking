from fastapi import APIRouter, Depends, Query
from typing import List
from datetime import date
from sqlmodel import Session

from app.core.database import get_session
from app.schemas.showtime import ShowtimeRead, ShowtimeDetailRead
from app.services.showtime_service import ShowtimeService

router = APIRouter(prefix="/showtimes", tags=["Showtimes"])

@router.get("", response_model=List[ShowtimeRead])
def get_showtimes(
    film_id: int = Query(...),
    theater_id: int = Query(...),
    date: date = Query(...),
    db: Session = Depends(get_session),
):
    return ShowtimeService.get_showtimes(
        db=db,
        film_id=film_id,
        theater_id=theater_id,
        show_date=date,
    )

@router.get("/{showtime_id}", response_model=ShowtimeDetailRead)
def get_showtime_by_id(
    showtime_id: int,
    db: Session = Depends(get_session),
):
    return ShowtimeService.get_showtime_by_id(db=db, showtime_id=showtime_id)


