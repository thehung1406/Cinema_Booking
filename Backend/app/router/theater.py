from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.schemas.theater import TheaterRead
from app.services.theater_service import TheaterService

router = APIRouter(prefix="/theater", tags=["Theater"])

@router.get("/",response_model=List[TheaterRead])
def get_theaters(db:Session=Depends(get_session)):
    return TheaterService.get_all_theaters(db)

@router.get("/{theater_id}",response_model=TheaterRead)
def get_theater(theater_id:int,db:Session=Depends(get_session)):
    return TheaterService.get_theater_by_id(db,theater_id)
@router.get("/{film_id}", response_model=List[TheaterRead])
def get_theaters_by_film(
    film_id: int,
    db: Session = Depends(get_session),
):
    return TheaterService.get_theaters_by_film(db, film_id)