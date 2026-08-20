from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.core.database import get_session
from app.schemas.cinema_room import CinemaRoomRead
from app.services.cinema_room_service import CinemaRoomService

router = APIRouter(prefix="/cinema-rooms", tags=["Cinema Rooms"])


@router.get("/", response_model=List[CinemaRoomRead])
def list_cinema_rooms(
    theater_id: Optional[int] = Query(default=None, description="Lọc danh sách phòng theo cụm rạp"),
    skip: int = Query(default=0, ge=0, description="Số bản ghi bỏ qua"),
    limit: int = Query(default=50, ge=1, le=200, description="Số bản ghi tối đa"),
    db: Session = Depends(get_session),
):
    if theater_id is not None:
        return CinemaRoomService.get_rooms_by_theater(db, theater_id, skip=skip, limit=limit)
    return CinemaRoomService.get_all_rooms(db, skip=skip, limit=limit)


@router.get("/theater/{theater_id}", response_model=List[CinemaRoomRead])
def list_cinema_rooms_by_theater(theater_id: int, db: Session = Depends(get_session)):
    return CinemaRoomService.get_rooms_by_theater(db, theater_id)


@router.get("/{room_id}", response_model=CinemaRoomRead)
def get_cinema_room(room_id: int, db: Session = Depends(get_session)):
    room = CinemaRoomService.get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Cinema room not found")
    return room

