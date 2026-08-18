from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.core.database import get_session
from app.schemas.cinema_room import CinemaRoomRead
from app.services.cinema_room_service import CinemaRoomService

router = APIRouter(prefix="/cinema_rooms", tags=["cinema_rooms"])


@router.get("/", response_model=List[CinemaRoomRead])
def list_cinema_rooms(
    theater_id: Optional[int] = Query(default=None, description="Lọc danh sách phòng theo cụm rạp"),
    db: Session = Depends(get_session),
):
    if theater_id is not None:
        return CinemaRoomService.get_rooms_by_theater(db, theater_id)
    return CinemaRoomService.get_all_rooms(db)


@router.get("/theater/{theater_id}", response_model=List[CinemaRoomRead])
def list_cinema_rooms_by_theater(theater_id: int, db: Session = Depends(get_session)):
    return CinemaRoomService.get_rooms_by_theater(db, theater_id)


@router.get("/{room_id}", response_model=CinemaRoomRead)
def get_cinema_room(room_id: int, db: Session = Depends(get_session)):
    room = CinemaRoomService.get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Cinema room not found")
    return room
