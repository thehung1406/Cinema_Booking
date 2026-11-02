from contextlib import asynccontextmanager
from secrets import compare_digest
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from sqlalchemy import create_engine, func, or_, text
from sqlmodel import Session, select

from cinema_platform.auth import AuthClient, AuthError
from cinema_platform.logging import service_logger
from .config import Settings
from . import service
from .models import Review, ReviewSentiment, utcnow
from .read_client import ReadClient
from .schemas import ReviewWrite, ReviewEdit, ReviewRead, ModerationWrite
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field, model_validator


def create_app(settings=None, *, engine=None, auth_transport=None, read_transport=None):
    settings = settings or Settings()
    own_engine = engine is None
    engine = engine or create_engine(settings.database_url, pool_pre_ping=True)
    logger = service_logger("review")

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(trust_env=False, transport=auth_transport) as auth_http:
            with httpx.Client(trust_env=False, transport=read_transport, timeout=5) as read_http:
                app.state.auth = AuthClient(auth_http, settings.identity_origin, settings.service_key)
                app.state.read_http = read_http
                yield
        if own_engine:
            engine.dispose()

    app = FastAPI(title="Cinema Review", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def context(request, call_next):
        request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Service-Name"] = "review"
        logger.info("method=%s status=%s request_id=%s", request.method, response.status_code, request_id)
        return response

    def reader():
        return ReadClient(app.state.read_http, settings)

    def db_session():
        with Session(engine) as db:
            yield db

    async def current_user(authorization: str = Header(default="")):
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "Bearer token required")
        try:
            return await app.state.auth.introspect(token)
        except AuthError as exc:
            raise HTTPException(exc.status_code, "Không thể xác thực truy cập Review") from exc

    async def staff_user(user=Depends(current_user)):
        if "reviews.moderate" not in user.permissions:
            raise HTTPException(403, "Bạn không có quyền kiểm duyệt đánh giá")
        return user

    def writes():
        if not settings.writes_enabled:
            raise HTTPException(503, "Review đang chuyển dữ liệu; chưa mở quyền ghi")

    def private(x_service_key: str = Header(default="")):
        if len(settings.service_key) < 32:
            raise HTTPException(503, "Service credential is not configured")
        if not compare_digest(x_service_key.encode(), settings.service_key.encode()):
            raise HTTPException(401, "Invalid service credential")

    @app.get("/health/live")
    def live():
        return {"status": "ok", "service": "review"}

    @app.get("/health/ready")
    def ready():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse({"status": "not_ready", "service": "review"}, status_code=503)
        return {"status": "ready", "service": "review"}

    @app.get("/internal/v1/migration/state", dependencies=[Depends(private)], include_in_schema=False)
    def migration_state():
        return {"writes_enabled": settings.writes_enabled}

    def present(db, rows, viewer_id=None):
        # Load own results then release the read transaction before the external author API.
        payload = []
        for row in rows:
            result = db.get(ReviewSentiment, row.id)
            current = result is not None and result.content_version == row.content_version
            payload.append(dict(id=row.id, content=row.content, content_version=row.content_version,
                moderation_status=row.moderation_status, updated_at=row.updated_at,
                analysis_status=result.status if current else "pending",
                sentiment=result.label if current and result.status == "succeeded" else None,
                user_id=row.user_id, film_id=row.film_id, is_owner=viewer_id == row.user_id))
        # Only primitive copies cross the transaction boundary.
        from types import SimpleNamespace
        db.rollback()
        authors = reader().authors([SimpleNamespace(**r) for r in payload])
        for item in payload:
            fact = authors[(item.pop("user_id"), item.pop("film_id"))]
            item.update(author=fact.author, verified_purchase=fact.verified_purchase)
        return payload

    def ranked(db, theater_id, show_date, window_days, limit, evening=False):
        films = reader().candidates(theater_id, show_date, evening)
        stats = service.summaries(db, [f.id for f in films], settings, window_days)
        result = [dict(film_id=f.id, title=f.title, image=f.image, summary=stats[f.id],
            booking_url=f"/ticket-booking?filmId={f.id}") for f in films if stats[f.id]["eligible"]]
        result.sort(key=lambda r: (-r["summary"]["score"], -r["summary"]["total"], r["film_id"]))
        return result[:limit]

    @app.get("/films/positive-trending")
    def trending(theater_id: int | None = Query(None, gt=0), show_date: date | None = None,
                 window_days: int = Query(settings.sentiment_window_days, ge=1, le=365),
                 limit: int = Query(12, ge=1, le=50), db=Depends(db_session)):
        return ranked(db, theater_id, show_date, window_days, limit)

    @app.get("/films/{film_id}/sentiment-summary")
    def summary(film_id: int, window_days: int = Query(settings.sentiment_window_days, ge=1, le=365), db=Depends(db_session)):
        reader().film(film_id)
        return service.summaries(db, [film_id], settings, window_days)[film_id]

    @app.get("/films/{film_id}/reviews", response_model=list[ReviewRead])
    def reviews(film_id: int, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50), db=Depends(db_session)):
        reader().film(film_id)
        rows = db.exec(select(Review).where(Review.film_id == film_id, Review.is_deleted == False,
            Review.moderation_status == "approved").order_by(Review.updated_at.desc(), Review.id.desc()).offset(skip).limit(limit)).all()
        return present(db, rows)

    @app.get("/films/{film_id}/reviews/mine", response_model=ReviewRead | None)
    def mine(film_id: int, user=Depends(current_user), db=Depends(db_session)):
        row = db.exec(select(Review).where(Review.film_id == film_id, Review.user_id == user.user_id, Review.is_deleted == False)).first()
        return present(db, [row], user.user_id)[0] if row else None

    @app.post("/films/{film_id}/reviews", response_model=ReviewRead, status_code=201, dependencies=[Depends(writes)])
    def create(film_id: int, body: ReviewWrite, user=Depends(current_user), db=Depends(db_session)):
        reader().film(film_id)
        return present(db, [service.create_review(db, film_id, user.user_id, body.content, settings)], user.user_id)[0]

    @app.patch("/reviews/{review_id}", response_model=ReviewRead, dependencies=[Depends(writes)])
    def edit(review_id: int, body: ReviewEdit, user=Depends(current_user), db=Depends(db_session)):
        return present(db, [service.edit_review(db, review_id, user.user_id, body, settings)], user.user_id)[0]

    @app.delete("/reviews/{review_id}", status_code=204, dependencies=[Depends(writes)])
    def remove(review_id: int, user=Depends(current_user), db=Depends(db_session)):
        service.delete_review(db, review_id, user.user_id)
        return Response(status_code=204)

    @app.get("/reviews/moderation/pending", response_model=list[ReviewRead])
    def pending(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50), user=Depends(staff_user), db=Depends(db_session)):
        rows = db.exec(select(Review).where(Review.is_deleted == False, Review.moderation_status == "pending")
            .order_by(Review.updated_at, Review.id).offset(skip).limit(limit)).all()
        return present(db, rows, user.user_id)

    @app.patch("/reviews/{review_id}/moderation", response_model=ReviewRead, dependencies=[Depends(writes)])
    def moderate(review_id: int, body: ModerationWrite, user=Depends(staff_user), db=Depends(db_session)):
        return present(db, [service.moderate_review(db, review_id, body)], user.user_id)[0]

    @app.post("/reviews/{review_id}/retry", response_model=ReviewRead, dependencies=[Depends(writes)])
    def retry(review_id: int, user=Depends(staff_user), db=Depends(db_session)):
        review = service.locked_review(db, review_id)
        if review.moderation_status != "approved":
            raise HTTPException(409, "Cần duyệt đánh giá trước khi phân tích lại")
        service.invalidate(db, review)
        db.commit()
        return present(db, [review], user.user_id)[0]

    @app.get("/internal/v1/positive-films", dependencies=[Depends(private)], include_in_schema=False)
    def positive(theater_id: int | None = None, show_date: date | None = None,
                 window_days: int = Query(settings.sentiment_window_days, ge=1, le=365),
                 limit: int = Query(12, ge=1, le=50), evening: bool = False, db=Depends(db_session)):
        return ranked(db, theater_id, show_date, window_days, limit, evening)

    @app.post("/internal/v1/report-sentiments", dependencies=[Depends(private)], include_in_schema=False)
    def report(body: ReportInput, db=Depends(db_session)):
        return report_sentiments(db, body)

    return app


class ReportInput(BaseModel):
    start_date: date
    end_date: date
    film_ids: list[int] | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def dates(self):
        if self.end_date < self.start_date or (self.end_date-self.start_date).days > 366:
            raise ValueError("Invalid report date range")
        return self


def report_sentiments(db, body):
    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    begin = datetime.combine(body.start_date, time.min, tzinfo=tz)
    end = datetime.combine(body.end_date+timedelta(days=1), time.min, tzinfo=tz)
    conditions = [Review.is_deleted == False, Review.moderation_status == "approved",
        Review.updated_at >= begin, Review.updated_at < end, Review.updated_at <= utcnow()]
    if body.film_ids is not None:
        conditions.append(Review.film_id.in_(body.film_ids))
    total = db.exec(select(func.count(Review.id)).where(*conditions)).one()
    rows = db.exec(select(ReviewSentiment.label, func.count(Review.id)).join(Review, Review.id == ReviewSentiment.review_id).where(
        *conditions, Review.content_version == ReviewSentiment.content_version, ReviewSentiment.status == "succeeded",
        ReviewSentiment.label.in_(["positive", "neutral", "negative"])).group_by(ReviewSentiment.label)).all()
    result = dict(positive=0, neutral=0, negative=0)
    result.update(dict(rows))
    analyzed = sum(result.values())
    return {**result, "total": total, "pending": total-analyzed, "coverage": round(100*analyzed/total, 2) if total else 0}


def application():
    return create_app()
