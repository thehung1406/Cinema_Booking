from contextlib import asynccontextmanager

from uuid import uuid4

import httpx

from fastapi import FastAPI

from sqlalchemy import create_engine

from cinema_platform.auth import AuthClient

from cinema_platform.logging import service_logger

from .config import Settings

from .router.api import create_router


def create_app(settings=None, *, transport=None, engine=None):
    settings = settings or Settings()
    engine = engine or create_engine(settings.database_url, pool_pre_ping=True)

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(trust_env=False, transport=transport) as http:
            app.state.auth = AuthClient(
                http, settings.identity_origin, settings.service_key
            )
            yield
        engine.dispose()

    app = FastAPI(
        title="Cinema Notification",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    logger = service_logger("notification")

    @app.middleware("http")
    async def context(request, call_next):
        request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "method=%s status=%s request_id=%s",
            request.method,
            response.status_code,
            request_id,
        )
        return response

    app.include_router(create_router(app, engine, settings, logger))
    return app


def application():
    return create_app()
