"""Read-only facts owned by legacy Catalog/Identity/Booking during M4."""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from app.core.database import get_session
from app.models import Film, Booking, Showtime
from app.router.internal_auth import internal_service
from app.services.review_service import future_showtimes

router = APIRouter(prefix="/internal/v1/review-read", include_in_schema=False, dependencies=[Depends(internal_service)])


@router.get("/films/{film_id}")
def film(film_id: int, db: Session = Depends(get_session)):
    from app.services.catalog_remote import get_film
    row = get_film(db, film_id)
    if row is None or row.deleted_at is not None:
        raise HTTPException(404, "Phim không tồn tại")
    return {"id": row.id, "title": row.title, "image": row.image}


class Author(BaseModel):
    user_id: int = Field(gt=0)
    film_id: int = Field(gt=0)


class Authors(BaseModel):
    items: list[Author] = Field(max_length=100)


@router.post("/authors")
def authors(body: Authors, db: Session = Depends(get_session)):
    from app.services.identity_remote import contact, profiles
    from app.utils.identity_ownership import get_owner
    ids = {item.user_id for item in body.items}
    if get_owner(db) == "service":
        names = {user_id: user.username for user_id, user in profiles(ids).items()}
    else:
        names = {user_id: contact(db, user_id).username for user_id in ids}
    from app.utils.booking_ownership import get_owner as booking_owner
    remote_purchases=None
    if booking_owner(db)=="service":
        from app.services.booking_remote import call
        facts=call("POST","/internal/v1/booking-read/verified",json={"items":[item.model_dump() for item in body.items]})
        remote_purchases={(r["user_id"],r["film_id"]):r["verified_purchase"] for r in facts}
    result = []
    for item in body.items:
        username = names.get(item.user_id)
        from app.utils.cinema_ownership import get_owner as cinema_owner
        if remote_purchases is not None:
            verified=remote_purchases.get((item.user_id,item.film_id),False)
        elif cinema_owner(db)=="service":
            from app.models.sales import SalesConfiguration as Config
            from sqlalchemy import and_
            verified=db.exec(select(Booking.id).join(Config,and_(Config.showtime_id==Booking.showtime_id,Config.sales_version==Booking.sales_version)).where(
                Booking.user_id==item.user_id,Config.film_id==item.film_id,Booking.payment_status=="PAID").limit(1)).first() is not None
        else:
            verified = db.exec(select(Booking.id).join(Showtime, Showtime.id == Booking.showtime_id).where(
                Booking.user_id == item.user_id, Showtime.film_id == item.film_id,
                Booking.payment_status == "PAID").limit(1)).first() is not None
        result.append({"user_id": item.user_id, "film_id": item.film_id,
            "author": username or "Khán giả", "verified_purchase": verified})
    return result


@router.get("/candidates")
def candidates(theater_id: int | None = None, show_date: date | None = None, evening: bool = False,
               db: Session = Depends(get_session)):
    from app.utils.booking_ownership import get_owner as booking_owner
    if booking_owner(db)=="service":
        from app.services.booking_remote import call
        from app.services.catalog_remote import film_batch
        params={"evening":str(evening).lower()}
        if theater_id: params["theater_id"]=theater_id
        if show_date: params["show_date"]=show_date.isoformat()
        ids=call("GET","/internal/v1/booking-read/candidates",params=params)
        return [{"id":r.id,"title":r.title,"image":r.image} for r in film_batch(ids).values()]
    shows = future_showtimes(db, theater_id=theater_id, show_date=show_date, evening=evening).subquery()
    from app.utils.catalog_ownership import get_owner
    if get_owner(db) == "service":
        from app.services.catalog_remote import film_batch
        ids = db.exec(select(shows.c.film_id).distinct()).all()
        rows = list(film_batch(ids).values())
    else:
        rows = db.exec(select(Film).where(Film.id.in_(select(shows.c.film_id).distinct()))).all()
    return [{"id": row.id, "title": row.title, "image": row.image} for row in rows]


@router.get("/ownership")
def ownership():
    from app.utils.review_ownership import get_owner
    return {"owner": get_owner()}
