"""HTTP routes and request dependencies for this owner. App lifecycle stays in main."""

from secrets import compare_digest
from threading import Lock

from fastapi import Depends, Header, HTTPException, Query, Response

from fastapi.responses import JSONResponse

from sqlalchemy import func, text

from sqlmodel import Session, select

from cinema_platform.auth import AuthError

from .. import service

from ..models import Review, ReviewSentiment, utcnow

from ..read_client import ReadClient

from ..schemas import ReviewWrite, ReviewEdit, ReviewRead, ModerationWrite, SentimentDecisionWrite, SentimentRetryWrite

from datetime import date, datetime, time, timedelta

from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, model_validator

from fastapi import APIRouter


class ReportInput(BaseModel):
    start_date: date
    end_date: date
    film_ids: list[int] | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def dates(self):
        if (
            self.end_date < self.start_date
            or (self.end_date - self.start_date).days > 366
        ):
            raise ValueError("Invalid report date range")
        return self


def report_sentiments(db, body):
    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    begin = datetime.combine(body.start_date, time.min, tzinfo=tz)
    end = datetime.combine(body.end_date + timedelta(days=1), time.min, tzinfo=tz)
    conditions = [
        Review.is_deleted == False,
        Review.moderation_status == "approved",
        Review.updated_at >= begin,
        Review.updated_at < end,
        Review.updated_at <= utcnow(),
    ]
    if body.film_ids is not None:
        conditions.append(Review.film_id.in_(body.film_ids))
    total = db.exec(select(func.count(Review.id)).where(*conditions)).one()
    rows = db.exec(
        select(ReviewSentiment.label, func.count(Review.id))
        .join(Review, Review.id == ReviewSentiment.review_id)
        .where(
            *conditions,
            Review.content_version == ReviewSentiment.content_version,
            ReviewSentiment.status == "succeeded",
            ReviewSentiment.label.in_(["positive", "neutral", "negative"]),
        )
        .group_by(ReviewSentiment.label)
    ).all()
    result = dict(positive=0, neutral=0, negative=0)
    result.update(dict(rows))
    analyzed = sum(result.values())
    return {
        **result,
        "total": total,
        "pending": total - analyzed,
        "coverage": round(100 * analyzed / total, 2) if total else 0,
    }


def create_router(app, engine, settings, logger):
    router = APIRouter()
    demo_lock = Lock()
    demo_enabled = bool(settings.sentiment_demo_lr_path and settings.sentiment_demo_visobert_path)

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
            raise HTTPException(
                exc.status_code, "Không thể xác thực truy cập Review"
            ) from exc

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

    @router.get("/health/live")
    def live():
        return {"status": "ok", "service": "review"}

    @router.get("/health/ready")
    def ready():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(
                {"status": "not_ready", "service": "review"}, status_code=503
            )
        return {"status": "ready", "service": "review"}

    @router.get(
        "/internal/v1/migration/state",
        dependencies=[Depends(private)],
        include_in_schema=False,
    )
    def migration_state():
        return {"writes_enabled": settings.writes_enabled}

    def present(db, rows, viewer_id=None):
        # Load own results then release the read transaction before the external author API.
        payload = []
        for row in rows:
            result = db.get(ReviewSentiment, row.id)
            current = (
                result is not None and result.content_version == row.content_version
            )
            payload.append(
                dict(
                    id=row.id,
                    content=row.content,
                    content_version=row.content_version,
                    moderation_status=row.moderation_status,
                    updated_at=row.updated_at,
                    analysis_status=result.status if current else "pending",
                    sentiment=(
                        result.label
                        if current and result.status == "succeeded"
                        else None
                    ),
                    user_id=row.user_id,
                    film_id=row.film_id,
                    is_owner=viewer_id == row.user_id,
                )
            )
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
        result = [
            dict(
                film_id=f.id,
                title=f.title,
                image=f.image,
                summary=stats[f.id],
                booking_url=f"/ticket-booking?filmId={f.id}",
            )
            for f in films
            if stats[f.id]["eligible"]
        ]
        result.sort(
            key=lambda r: (-r["summary"]["score"], -r["summary"]["total"], r["film_id"])
        )
        return result[:limit]

    @router.get("/films/positive-trending")
    def trending(
        theater_id: int | None = Query(None, gt=0),
        show_date: date | None = None,
        window_days: int = Query(settings.sentiment_window_days, ge=1, le=365),
        limit: int = Query(12, ge=1, le=50),
        evening: bool = False,
        db=Depends(db_session),
    ):
        return ranked(db, theater_id, show_date, window_days, limit, evening)

    @router.get("/films/{film_id}/sentiment-summary")
    def summary(
        film_id: int,
        window_days: int = Query(settings.sentiment_window_days, ge=1, le=365),
        db=Depends(db_session),
    ):
        reader().film(film_id)
        return service.summaries(db, [film_id], settings, window_days)[film_id]

    @router.get("/films/{film_id}/reviews", response_model=list[ReviewRead])
    def reviews(
        film_id: int,
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=50),
        db=Depends(db_session),
    ):
        reader().film(film_id)
        rows = db.exec(
            select(Review)
            .where(
                Review.film_id == film_id,
                Review.is_deleted == False,
                Review.moderation_status == "approved",
            )
            .order_by(Review.updated_at.desc(), Review.id.desc())
            .offset(skip)
            .limit(limit)
        ).all()
        return present(db, rows)

    @router.get("/films/{film_id}/reviews/mine", response_model=ReviewRead | None)
    def mine(film_id: int, user=Depends(current_user), db=Depends(db_session)):
        row = db.exec(
            select(Review).where(
                Review.film_id == film_id,
                Review.user_id == user.user_id,
                Review.is_deleted == False,
            )
        ).first()
        return present(db, [row], user.user_id)[0] if row else None

    @router.post(
        "/films/{film_id}/reviews",
        response_model=ReviewRead,
        status_code=201,
        dependencies=[Depends(writes)],
    )
    def create(
        film_id: int,
        body: ReviewWrite,
        user=Depends(current_user),
        db=Depends(db_session),
    ):
        reader().film(film_id)
        return present(
            db,
            [service.create_review(db, film_id, user.user_id, body.content, settings)],
            user.user_id,
        )[0]

    @router.patch(
        "/reviews/{review_id}",
        response_model=ReviewRead,
        dependencies=[Depends(writes)],
    )
    def edit(
        review_id: int,
        body: ReviewEdit,
        user=Depends(current_user),
        db=Depends(db_session),
    ):
        return present(
            db,
            [service.edit_review(db, review_id, user.user_id, body, settings)],
            user.user_id,
        )[0]

    @router.delete(
        "/reviews/{review_id}", status_code=204, dependencies=[Depends(writes)]
    )
    def remove(review_id: int, user=Depends(current_user), db=Depends(db_session)):
        service.delete_review(db, review_id, user.user_id)
        return Response(status_code=204)

    @router.get("/reviews/moderation/pending", response_model=list[ReviewRead])
    def pending(
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=50),
        user=Depends(staff_user),
        db=Depends(db_session),
    ):
        rows = db.exec(
            select(Review)
            .where(Review.is_deleted == False, Review.moderation_status == "pending")
            .order_by(Review.updated_at, Review.id)
            .offset(skip)
            .limit(limit)
        ).all()
        return present(db, rows, user.user_id)

    @router.get("/reviews/sentiment/pending")
    def sentiment_pending(
        status: str = Query("needs_review", pattern="^(needs_review|succeeded|failed|pending)$"),
        film_id: int | None = Query(None, gt=0),
        offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
        user=Depends(staff_user), db=Depends(db_session),
    ):
        query = select(Review, ReviewSentiment).join(ReviewSentiment, Review.id == ReviewSentiment.review_id).where(
            Review.is_deleted == False, Review.moderation_status == "approved",
            Review.content_version == ReviewSentiment.content_version, ReviewSentiment.status == status)
        if film_id:
            query = query.where(Review.film_id == film_id)
        total = db.exec(select(func.count()).select_from(query.subquery())).one()
        rows = db.exec(query.order_by(ReviewSentiment.updated_at, Review.id).offset(offset).limit(limit)).all()
        return dict(items=[service.sentiment_item(review, result) for review, result in rows], total=total,
                    demo_enabled=demo_enabled)

    @router.post("/reviews/sentiment/demo")
    def sentiment_demo(body: ReviewWrite, user=Depends(staff_user)):
        if not demo_enabled:
            raise HTTPException(404, "Chưa bật chế độ so sánh mô hình")
        if not demo_lock.acquire(blocking=False):
            raise HTTPException(429, "Đang chạy một lượt so sánh; vui lòng thử lại")
        from ..predictor import load_predictor, validate_scores
        try:
            predictions = []
            for name, backend, path in (
                ("TF-IDF + Logistic Regression", "sklearn", settings.sentiment_demo_lr_path),
                ("ViSoBERT", "transformers", settings.sentiment_demo_visobert_path),
            ):
                predict, version = load_predictor(backend, path)
                scores = predict(body.content)
                validate_scores(scores)
                label = max(scores, key=scores.get)
                predictions.append(dict(model=name, model_version=version, label=label, scores=scores,
                                        needs_review=scores[label] < settings.sentiment_review_threshold))
        except Exception as exc:
            logger.error("sentiment_demo_failed error_type=%s", type(exc).__name__)
            raise HTTPException(503, "Chưa chạy được hai mô hình demo") from exc
        finally:
            demo_lock.release()
        return {"predictions": predictions}

    @router.post("/reviews/{review_id}/sentiment-decision", dependencies=[Depends(writes)])
    def sentiment_decision(review_id: int, body: SentimentDecisionWrite,
                           user=Depends(staff_user), db=Depends(db_session)):
        return service.decide_sentiment(db, review_id, user.user_id, body)

    @router.get("/reviews/{review_id}/sentiment-decisions")
    def sentiment_decisions(review_id: int, limit: int = Query(50, ge=1, le=100),
                            user=Depends(staff_user), db=Depends(db_session)):
        from ..models import SentimentDecision
        rows = db.exec(select(SentimentDecision).where(SentimentDecision.review_id == review_id)
                       .order_by(SentimentDecision.id.desc()).limit(limit)).all()
        return [dict(id=row.id, actor_user_id=row.actor_user_id, content_version=row.content_version,
                     label=row.label, previous_label=row.previous_label, reason=row.reason,
                     created_at=row.created_at) for row in rows]

    @router.patch(
        "/reviews/{review_id}/moderation",
        response_model=ReviewRead,
        dependencies=[Depends(writes)],
    )
    def moderate(
        review_id: int,
        body: ModerationWrite,
        user=Depends(staff_user),
        db=Depends(db_session),
    ):
        return present(
            db, [service.moderate_review(db, review_id, body)], user.user_id
        )[0]

    @router.post(
        "/reviews/{review_id}/retry",
        response_model=ReviewRead,
        dependencies=[Depends(writes)],
    )
    def retry(review_id: int, body: SentimentRetryWrite | None = None, user=Depends(staff_user), db=Depends(db_session)):
        review = service.locked_review(db, review_id)
        if review.moderation_status != "approved":
            raise HTTPException(409, "Cần duyệt đánh giá trước khi phân tích lại")
        current = db.get(ReviewSentiment, review_id, with_for_update=True)
        if current and current.decision_source == "staff":
            if body is None:
                raise HTTPException(422, "Cần lý do để phân tích lại nhãn nhân viên đã xác nhận")
            from ..models import SentimentDecision
            from uuid import uuid4
            db.add(SentimentDecision(review_id=review_id, actor_user_id=user.user_id, request_id=str(uuid4()),
                content_version=review.content_version, analysis_generation=current.analysis_generation,
                previous_label=current.label, label="retry", reason=body.reason, request_digest="retry",
                response={"action": "retry"}))
        service.invalidate(db, review)
        db.commit()
        return present(db, [review], user.user_id)[0]

    @router.get(
        "/internal/v1/positive-films",
        dependencies=[Depends(private)],
        include_in_schema=False,
    )
    def positive(
        theater_id: int | None = None,
        show_date: date | None = None,
        window_days: int = Query(settings.sentiment_window_days, ge=1, le=365),
        limit: int = Query(12, ge=1, le=50),
        evening: bool = False,
        db=Depends(db_session),
    ):
        return ranked(db, theater_id, show_date, window_days, limit, evening)

    @router.post(
        "/internal/v1/report-sentiments",
        dependencies=[Depends(private)],
        include_in_schema=False,
    )
    def report(body: ReportInput, db=Depends(db_session)):
        return report_sentiments(db, body)

    from cinema_platform.reporting import source_router

    router.include_router(source_router(engine, settings.service_key, "review"))
    return router
