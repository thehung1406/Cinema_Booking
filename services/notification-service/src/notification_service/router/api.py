"""HTTP routes and request dependencies for this owner. App lifecycle stays in main."""

from secrets import compare_digest

from fastapi import Depends, Header, HTTPException

from fastapi.responses import JSONResponse

from pydantic import BaseModel, Field

from sqlalchemy import func, select, text

from sqlalchemy.orm import Session

from cinema_platform.auth import AuthError

from ..delivery import retry_job

from ..models import DeliveryJob

from fastapi import APIRouter


def create_router(app, engine, settings, logger):
    router = APIRouter()

    async def operator(
        authorization: str = Header(default=""), x_service_key: str = Header(default="")
    ):
        if len(settings.service_key) < 32:
            raise HTTPException(503, "Service credential is not configured")
        if not compare_digest(x_service_key.encode(), settings.service_key.encode()):
            raise HTTPException(401, "Invalid service credential")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "Bearer token required")
        try:
            return await app.state.auth.introspect(token, "notifications.manage")
        except AuthError as exc:
            raise HTTPException(
                exc.status_code, "Notification operation is not authorized"
            ) from exc

    @router.get("/health/live")
    def live():
        return {"status": "ok", "service": "notification"}

    @router.get("/health/ready")
    def ready():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(
                {"status": "not_ready", "service": "notification"}, status_code=503
            )
        return {"status": "ready", "service": "notification"}

    @router.get("/internal/v1/deliveries/summary")
    def summary(user=Depends(operator)):
        with Session(engine) as db:
            return {
                "counts": dict(
                    db.execute(
                        select(DeliveryJob.status, func.count()).group_by(
                            DeliveryJob.status
                        )
                    ).all()
                )
            }

    class RetryRequest(BaseModel):
        reason: str = Field(min_length=1, max_length=500, pattern=r".*\S.*")

    @router.post("/internal/v1/deliveries/{job_id}/retry")
    def retry(job_id: str, body: RetryRequest, user=Depends(operator)):
        try:
            with Session(engine) as db, db.begin():
                retry_job(db, job_id, str(user.user_id), body.reason)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"status": "queued", "job_id": job_id}

    return router
