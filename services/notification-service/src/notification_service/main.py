from contextlib import asynccontextmanager
from secrets import compare_digest
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from cinema_platform.auth import AuthClient, AuthError
from cinema_platform.logging import service_logger
from .config import Settings
from .delivery import retry_job
from .models import DeliveryJob


def create_app(settings=None, *, transport=None, engine=None):
    settings = settings or Settings()
    engine = engine or create_engine(settings.database_url, pool_pre_ping=True)

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(trust_env=False, transport=transport) as http:
            app.state.auth = AuthClient(http, settings.identity_origin, settings.service_key)
            yield
        engine.dispose()

    app = FastAPI(title="Cinema Notification", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    logger = service_logger("notification")

    @app.middleware("http")
    async def context(request, call_next):
        request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info("method=%s status=%s request_id=%s", request.method, response.status_code, request_id)
        return response

    async def operator(authorization: str = Header(default=""), x_service_key: str = Header(default="")):
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
            raise HTTPException(exc.status_code, "Notification operation is not authorized") from exc

    @app.get("/health/live")
    def live():
        return {"status": "ok", "service": "notification"}

    @app.get("/health/ready")
    def ready():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse({"status": "not_ready", "service": "notification"}, status_code=503)
        return {"status": "ready", "service": "notification"}

    @app.get("/internal/v1/deliveries/summary")
    def summary(user=Depends(operator)):
        with Session(engine) as db:
            return {"counts": dict(db.execute(select(DeliveryJob.status, func.count()).group_by(DeliveryJob.status)).all())}

    class RetryRequest(BaseModel):
        reason: str = Field(min_length=1, max_length=500, pattern=r".*\S.*")

    @app.post("/internal/v1/deliveries/{job_id}/retry")
    def retry(job_id: str, body: RetryRequest, user=Depends(operator)):
        try:
            with Session(engine) as db, db.begin():
                retry_job(db, job_id, str(user.user_id), body.reason)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"status": "queued", "job_id": job_id}

    return app


def application():
    return create_app()
