"""HTTP routes and request dependencies for this owner. App lifecycle stays in main."""

from datetime import datetime, timezone

from secrets import compare_digest

from zoneinfo import ZoneInfo

import unicodedata

from fastapi import Depends, Header, HTTPException, Query

from fastapi.responses import JSONResponse

from sqlalchemy import select, func, text

from sqlalchemy.orm import Session

from cinema_platform.auth import AuthError

from ..models import Film, Format, Genre, FoodQuote, ScheduleBinding, utcnow

from ..schemas import (
    FilmWrite,
    FilmIds,
    FilmSearch,
    FilmMatch,
    BindingRequest,
    BindingReference,
    QuoteRequest,
    FoodItemRead,
    FoodWrite,
    FilmRead,
    FilmDetailRead,
)

from .. import service

from fastapi import APIRouter

MANAGEMENT = {
    "films.manage",
    "rooms.manage",
    "showtimes.manage",
    "seat_types.manage",
    "users.manage",
    "roles.manage",
    "knowledge.manage",
    "reports.view",
}


def create_router(app, engine, settings, logger):
    router = APIRouter()

    def database():
        with Session(engine) as db:
            yield db

    def private(x_service_key: str = Header(default="")):
        if len(settings.service_key) < 32:
            raise HTTPException(503, "Catalog service credential is not configured")
        if not compare_digest(x_service_key.encode(), settings.service_key.encode()):
            raise HTTPException(401, "Invalid service credential")

    def writes():
        if not settings.writes_enabled:
            raise HTTPException(503, "Catalog đang chuyển dữ liệu")

    async def user(authorization: str = Header(default="")):
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "Bearer token required")
        try:
            return await app.state.auth.introspect(token)
        except AuthError as exc:
            raise HTTPException(exc.status_code, "Không thể xác thực Catalog") from exc

    async def admin(principal=Depends(user)):
        if "films.manage" not in principal.permissions:
            raise HTTPException(403, "Bạn không có quyền quản lý Catalog")
        return principal

    async def management(principal=Depends(user)):
        if not MANAGEMENT.intersection(principal.permissions):
            raise HTTPException(403, "Bạn không có quyền truy cập trang quản trị")
        return principal

    @router.get("/health/live")
    def live():
        return {"status": "ok", "service": "catalog"}

    @router.get("/health/ready")
    def ready():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM films LIMIT 0"))
        except Exception:
            return JSONResponse(
                {"status": "not_ready", "service": "catalog"}, status_code=503
            )
        return {"status": "ready", "service": "catalog"}

    @router.get(
        "/internal/v1/migration/state",
        dependencies=[Depends(private)],
        include_in_schema=False,
    )
    def migration_state():
        return {"writes_enabled": settings.writes_enabled}

    @router.get("/films/", response_model=list[FilmRead])
    def films(
        now_showing: bool = False,
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        db=Depends(database),
    ):
        query = select(Film).where(Film.deleted_at.is_(None))
        if now_showing:
            today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
            query = query.where(Film.release_date <= today, Film.end_date >= today)
        return [
            service.film_data(f)
            for f in db.scalars(query.order_by(Film.id).offset(skip).limit(limit))
        ]

    @router.get("/films/{film_id}", response_model=FilmDetailRead)
    def film(film_id: int, db=Depends(database)):
        return service.film_data(service.get_film(db, film_id))

    @router.get("/food-items", response_model=list[FoodItemRead])
    def menu(db=Depends(database)):
        return service.menu(db)

    @router.post("/food-items/quote", dependencies=[Depends(writes)])
    def public_quote(body: QuoteRequest, principal=Depends(user), db=Depends(database)):
        return service.quote_data(service.quote(db, body.selections, settings))

    @router.get("/admin/films")
    def admin_films(
        q: str = Query("", max_length=100),
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        principal=Depends(admin),
        db=Depends(database),
    ):
        query = select(Film).where(Film.deleted_at.is_(None))
        if q:
            query = query.where(Film.title.icontains(q, autoescape=True))
        total = db.scalar(
            select(func.count()).select_from(query.order_by(None).subquery())
        )
        return {
            "items": [
                service.film_data(f)
                for f in db.scalars(
                    query.order_by(Film.id.desc()).offset(offset).limit(limit)
                )
            ],
            "total": total,
        }

    @router.post("/admin/films", status_code=201, dependencies=[Depends(writes)])
    def create_film(body: FilmWrite, principal=Depends(admin), db=Depends(database)):
        return service.film_data(service.film_write(db, body))

    @router.put("/admin/films/{film_id}", dependencies=[Depends(writes)])
    def update_film(
        film_id: int, body: FilmWrite, principal=Depends(admin), db=Depends(database)
    ):
        return service.film_data(service.film_write(db, body, film_id))

    @router.delete("/admin/films/{film_id}", dependencies=[Depends(writes)])
    def retire_film(film_id: int, principal=Depends(admin), db=Depends(database)):
        return service.retire_film(db, film_id)

    @router.get("/admin/catalog")
    def references(principal=Depends(management), db=Depends(database)):
        return dict(
            genres=[
                dict(id=g.id, name=g.name)
                for g in db.scalars(select(Genre).order_by(Genre.name))
            ],
            formats=[
                dict(id=f.id, code=f.code, name=f.name)
                for f in db.scalars(select(Format).order_by(Format.name))
            ],
            films=[
                service.film_data(f)
                for f in db.scalars(
                    select(Film).where(Film.deleted_at.is_(None)).order_by(Film.title)
                )
            ],
        )

    @router.post("/admin/food-items", status_code=201, dependencies=[Depends(writes)])
    def create_food(body: FoodWrite, principal=Depends(admin), db=Depends(database)):
        return service.food_write(db, body)

    @router.put("/admin/food-items/{food_id}", dependencies=[Depends(writes)])
    def update_food(
        food_id: int, body: FoodWrite, principal=Depends(admin), db=Depends(database)
    ):
        return service.food_write(db, body, food_id)

    @router.post(
        "/internal/v1/films/batch",
        dependencies=[Depends(private)],
        include_in_schema=False,
    )
    def batch(body: FilmIds, db=Depends(database)):
        query = select(Film).where(Film.id.in_(set(body.ids)))
        if not body.include_retired:
            query = query.where(Film.deleted_at.is_(None))
        return [service.film_data(f) for f in db.scalars(query.order_by(Film.id))]

    @router.post(
        "/internal/v1/films/search",
        dependencies=[Depends(private)],
        include_in_schema=False,
    )
    def search(body: FilmSearch, db=Depends(database)):
        query = select(Film).where(Film.deleted_at.is_(None))
        if body.q:
            query = query.where(Film.title.icontains(body.q, autoescape=True))
        if body.genre:
            query = query.where(Film.genre_items.any(Genre.name.icontains(body.genre, autoescape=True)))
        if body.language:
            query = query.where(Film.language.icontains(body.language, autoescape=True))
        if body.duration_max:
            query = query.where(Film.duration_minutes <= body.duration_max)
        if body.now_showing:
            today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
            query = query.where(Film.release_date <= today, Film.end_date >= today)
        return [
            service.film_data(f)
            for f in db.scalars(
                query.order_by(Film.id).offset(body.skip).limit(body.limit)
            )
        ]

    @router.post(
        "/internal/v1/films/matches",
        dependencies=[Depends(private)],
        include_in_schema=False,
    )
    def matches(body: FilmMatch, db=Depends(database)):
        from ..matching import title_mentioned
        rows = db.execute(select(Film.id, Film.title).where(Film.deleted_at.is_(None)))
        return [
            dict(id=i, name=name)
            for i, name in rows
            if title_mentioned(body.message, name)
        ]

    @router.post(
        "/internal/v1/schedule-bindings",
        dependencies=[Depends(private), Depends(writes)],
        include_in_schema=False,
    )
    def bind(body: BindingRequest, db=Depends(database)):
        row = service.bind_schedule(db, body)
        return dict(
            id=row.id, film_version=row.film_version, film_snapshot=row.film_snapshot
        )

    @router.post(
        "/internal/v1/schedule-bindings/{binding_id}/{action}",
        dependencies=[Depends(private), Depends(writes)],
        include_in_schema=False,
    )
    def reference(
        binding_id: str, action: str, body: BindingReference, db=Depends(database)
    ):
        if action not in {"confirm", "release"}:
            raise HTTPException(404, "Unknown reference action")
        from ..models import BindingClosure

        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:id,1))"),
            {"id": binding_id},
        )
        closure = db.get(BindingClosure, binding_id)
        if closure:
            if action != "release" or closure.reference != body.reference:
                raise HTTPException(409, "Binding đã kết thúc")
            return {
                "id": binding_id,
                "reference": closure.reference,
                "state": "RELEASED",
            }
        row = db.scalar(
            select(ScheduleBinding)
            .where(ScheduleBinding.id == binding_id)
            .with_for_update()
        )
        if row is None:
            if action != "release":
                raise HTTPException(404, "Binding không tồn tại")
            db.add(BindingClosure(id=binding_id, reference=body.reference))
            service.save(db)
            return {"id": binding_id, "reference": body.reference, "state": "RELEASED"}
        if row.reference is not None and row.reference != body.reference:
            raise HTTPException(409, "Binding thuộc tham chiếu khác")
        if action == "confirm" and row.reference_state == "RELEASED":
            raise HTTPException(409, "Binding đã kết thúc")
        if action == "release":
            db.add(BindingClosure(id=binding_id, reference=body.reference))
        row.reference = body.reference
        row.reference_state = "CONFIRMED" if action == "confirm" else "RELEASED"
        service.save(db)
        return {"id": row.id, "reference": row.reference, "state": row.reference_state}

    @router.post(
        "/internal/v1/food-quotes",
        dependencies=[Depends(private), Depends(writes)],
        include_in_schema=False,
    )
    def quote(body: QuoteRequest, db=Depends(database)):
        return service.quote_data(service.quote(db, body.selections, settings))

    @router.get(
        "/internal/v1/food-quotes/{quote_id}",
        dependencies=[Depends(private)],
        include_in_schema=False,
    )
    def read_quote(quote_id: str, db=Depends(database)):
        row = db.get(FoodQuote, quote_id)
        if row is None:
            raise HTTPException(404, "Quote không tồn tại")
        expiry = (
            row.expires_at.replace(tzinfo=timezone.utc)
            if row.expires_at.tzinfo is None
            else row.expires_at
        )
        if expiry <= utcnow():
            raise HTTPException(409, "Quote đã hết hạn")
        return service.quote_data(row)

    from cinema_platform.reporting import source_router

    router.include_router(source_router(engine, settings.service_key, "catalog"))
    return router
