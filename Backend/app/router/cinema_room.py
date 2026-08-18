from typing import List

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.database import get_session
from app.schemas.cinema_room import CinemaRoomRead
from app.services.cinema_room_service import CinemaRoomService

router = APIRouter(prefix="/cinema_rooms", tags=["cinema_rooms"])


@router.get("/{theater_id}",response_model=List[CinemaRoomRead])
def list_cinema_rooms_by_theater(theater_id: int,db: Session = Depends(get_session)):
    return CinemaRoomService.get_rooms_by_theater(db, theater_id)

