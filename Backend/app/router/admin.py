"""Administration API for the VPP's UC01–UC07 workflows."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.models import (CinemaRoom, Film, Format, Genre, KnowledgeDocument,
    Permission, RolePermission, Seat, SeatType, Showtime, Theater)
from app.repositories import admin_repo as repo
from app.schemas.admin import (AccountStatus, DocumentApproval, DocumentWrite,
    EmployeeCreate, EmployeeWrite, FilmWrite, PriceWrite, ReportFilters, RoomWrite,
    SeatWrite, ShowtimeWrite)
from app.services import admin_service as service
from app.utils.dependencies import get_current_user, require_permission

router = APIRouter(prefix="/admin", tags=["Administration"])
MANAGEMENT_PERMISSIONS = {"films.manage", "rooms.manage", "showtimes.manage",
    "seat_types.manage", "users.manage", "roles.manage", "knowledge.manage", "reports.view"}
DB = Annotated[Session, Depends(get_session)]
Films = Annotated[object, Depends(require_permission("films.manage"))]
Rooms = Annotated[object, Depends(require_permission("rooms.manage"))]
Shows = Annotated[object, Depends(require_permission("showtimes.manage"))]
Prices = Annotated[object, Depends(require_permission("seat_types.manage"))]
Employees = Annotated[object, Depends(require_permission("users.manage"))]
Knowledge = Annotated[object, Depends(require_permission("knowledge.manage"))]
Reports = Annotated[object, Depends(require_permission("reports.view"))]


def user_permissions(db, user):
    return db.exec(select(Permission.code).join(RolePermission)
        .where(RolePermission.role_id == user.role_id).order_by(Permission.code)).all()


def management_user(db: DB, user=Depends(get_current_user)):
    if not MANAGEMENT_PERMISSIONS.intersection(user_permissions(db, user)):
        raise HTTPException(403, "Bạn không có quyền truy cập trang quản trị")
    return user


@router.get("/session")
def session(db: DB, user=Depends(management_user)):
    return {"user": dict(id=user.id, username=user.username, full_name=user.full_name,
        role=user.role), "permissions": user_permissions(db, user)}


@router.get("/catalog")
def catalog(db: DB, user=Depends(management_user)):
    return dict(genres=db.exec(select(Genre).order_by(Genre.name)).all(),
        formats=db.exec(select(Format).order_by(Format.name)).all(),
        theaters=db.exec(select(Theater).where(Theater.deleted_at.is_(None)).order_by(Theater.name)).all(),
        rooms=db.exec(select(CinemaRoom).where(CinemaRoom.deleted_at.is_(None)).order_by(CinemaRoom.name)).all(),
        films=[film_data(f) for f in db.exec(select(Film).where(Film.deleted_at.is_(None)).order_by(Film.title)).all()])


def film_data(film):
    return {**film.model_dump(), "genre_ids": [g.id for g in film.genre_items],
        "format_ids": [f.id for f in film.format_items]}


@router.get("/films")
def films(db: DB, user: Films, q: str = Query("", max_length=100),
          offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    result = repo.films(db, q, offset, limit)
    result["items"] = [film_data(f) for f in result["items"]]
    return result


@router.post("/films", status_code=201)
def create_film(body: FilmWrite, db: DB, user: Films):
    return film_data(service.film_write(db, body))


@router.put("/films/{film_id}")
def update_film(film_id: int, body: FilmWrite, db: DB, user: Films):
    return film_data(service.film_write(db, body, film_id))


@router.delete("/films/{film_id}")
def delete_film(film_id: int, db: DB, user: Films):
    return service.film_delete(db, film_id)


@router.get("/rooms")
def rooms(db: DB, user: Rooms, q: str = Query("", max_length=100),
          theater_id: int | None = Query(None, gt=0), offset: int = Query(0, ge=0),
          limit: int = Query(50, ge=1, le=200)):
    stmt = select(CinemaRoom).where(CinemaRoom.deleted_at.is_(None))
    if q:
        stmt = stmt.where(CinemaRoom.name.icontains(q, autoescape=True))
    if theater_id:
        stmt = stmt.where(CinemaRoom.theater_id == theater_id)
    return repo.page(db, stmt.order_by(CinemaRoom.id), offset, limit)


@router.post("/rooms", status_code=201)
def create_room(body: RoomWrite, db: DB, user: Rooms):
    return service.room_write(db, body)


@router.put("/rooms/{room_id}")
def update_room(room_id: int, body: RoomWrite, db: DB, user: Rooms):
    return service.room_write(db, body, room_id)


@router.delete("/rooms/{room_id}")
def delete_room(room_id: int, db: DB, user: Rooms):
    return service.room_delete(db, room_id)


@router.get("/rooms/{room_id}/seats")
def seats(room_id: int, db: DB, user: Rooms):
    room = service.get(db, CinemaRoom, room_id)
    return {"room": room, "seats": db.exec(select(Seat).where(Seat.room_id == room_id).order_by(Seat.seat_name)).all(),
        "seat_types": db.exec(select(SeatType).where(SeatType.room_id == room_id).order_by(SeatType.id)).all()}


@router.post("/rooms/{room_id}/seats", status_code=201)
def create_seat(room_id: int, body: SeatWrite, db: DB, user: Rooms):
    return service.seat_write(db, room_id, body)


@router.put("/rooms/{room_id}/seats/{seat_id}")
def update_seat(room_id: int, seat_id: int, body: SeatWrite, db: DB, user: Rooms):
    return service.seat_write(db, room_id, body, seat_id)


@router.delete("/rooms/{room_id}/seats/{seat_id}")
def delete_seat(room_id: int, seat_id: int, db: DB, user: Rooms):
    return service.seat_delete(db, room_id, seat_id)


@router.get("/showtimes")
def showtimes(db: DB, user: Shows, film_id: int | None = Query(None, gt=0),
              room_id: int | None = Query(None, gt=0), show_date: str | None = None,
              offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    from datetime import date
    stmt = select(Showtime)
    if film_id:
        stmt = stmt.where(Showtime.film_id == film_id)
    if room_id:
        stmt = stmt.where(Showtime.room_id == room_id)
    if show_date:
        try:
            day = date.fromisoformat(show_date)
        except ValueError:
            raise HTTPException(422, "Ngày chiếu không hợp lệ")
        stmt = stmt.where(Showtime.show_date == day)
    result = repo.page(db, stmt.order_by(Showtime.show_date.desc(), Showtime.start_time), offset, limit)
    result["items"] = [showtime_data(show) for show in result["items"]]
    return result


def showtime_data(show):
    return {**show.model_dump(exclude={"status"}), "status": show.status}


@router.post("/showtimes", status_code=201)
def create_showtime(body: ShowtimeWrite, db: DB, user: Shows):
    return showtime_data(service.showtime_write(db, body))


@router.put("/showtimes/{showtime_id}")
def update_showtime(showtime_id: int, body: ShowtimeWrite, db: DB, user: Shows):
    return showtime_data(service.showtime_write(db, body, showtime_id))


@router.delete("/showtimes/{showtime_id}")
def delete_showtime(showtime_id: int, db: DB, user: Shows):
    return service.showtime_delete(db, showtime_id)


@router.get("/prices")
def prices(db: DB, user: Prices, room_id: int | None = Query(None, gt=0),
           q: str = Query("", max_length=30), offset: int = Query(0, ge=0),
           limit: int = Query(50, ge=1, le=200)):
    stmt = select(SeatType).join(CinemaRoom).where(CinemaRoom.deleted_at.is_(None))
    if room_id:
        stmt = stmt.where(SeatType.room_id == room_id)
    if q:
        stmt = stmt.where(SeatType.name.icontains(q, autoescape=True))
    return repo.page(db, stmt.order_by(SeatType.room_id, SeatType.id), offset, limit)


@router.post("/prices", status_code=201)
def create_price(body: PriceWrite, db: DB, user: Prices):
    return service.price_write(db, body)


@router.put("/prices/{price_id}")
def update_price(price_id: int, body: PriceWrite, db: DB, user: Prices):
    return service.price_write(db, body, price_id)


@router.delete("/prices/{price_id}")
def delete_price(price_id: int, db: DB, user: Prices):
    price = service.get(db, SeatType, price_id, lock=True)
    if db.exec(select(Seat.id).where(Seat.seat_type_id == price_id).limit(1)).first():
        raise HTTPException(409, "Loại ghế đang có ghế sử dụng")
    return service.remove(db, price)


@router.get("/employees")
def employees(db: DB, user: Employees, q: str = Query("", max_length=100),
              offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    return repo.employees(db, q, offset, limit)


def employee_data(user):
    return dict(id=user.id, username=user.username, full_name=user.full_name,
        email=user.email, phone=user.phone, role_id=user.role_id, is_active=user.is_active)


@router.post("/employees", status_code=201)
def create_employee(body: EmployeeCreate, db: DB, user: Employees,
                    role_admin=Depends(require_permission("roles.manage"))):
    return employee_data(service.employee_create(db, body))


@router.put("/employees/{user_id}")
def update_employee(user_id: int, body: EmployeeWrite, db: DB, user: Employees):
    return employee_data(service.employee_write(db, user_id, body))


@router.put("/employees/{user_id}/status")
def account_status(user_id: int, body: AccountStatus, db: DB, user: Employees):
    return employee_data(service.account_status(db, user_id, body, user))


@router.get("/documents")
def documents(db: DB, user: Knowledge, q: str = Query("", max_length=100),
              offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    from sqlalchemy import or_
    stmt = select(KnowledgeDocument)
    if q:
        stmt = stmt.where(or_(KnowledgeDocument.title.icontains(q, autoescape=True),
            KnowledgeDocument.source_id.icontains(q, autoescape=True)))
    return repo.page(db, stmt.order_by(KnowledgeDocument.id.desc()), offset, limit)


@router.get("/documents/{document_id}")
def document_detail(document_id: int, db: DB, user: Knowledge):
    return service.document_detail(db, document_id)


@router.post("/documents")
def upsert_document(body: DocumentWrite, db: DB, user: Knowledge):
    return service.document_write(db, body)


@router.put("/documents/{document_id}/approval")
def approve_document(document_id: int, body: DocumentApproval, db: DB, user: Knowledge):
    return service.document_approve(db, document_id, body)


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, db: DB, user: Knowledge):
    return service.document_delete(db, document_id)


@router.get("/reports")
def reports(filters: Annotated[ReportFilters, Query()], db: DB, user: Reports):
    return repo.report(db, filters)
