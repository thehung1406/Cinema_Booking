from contextlib import asynccontextmanager

from uuid import uuid4

import httpx

from fastapi import FastAPI

from sqlalchemy import create_engine

from cinema_platform.auth import AuthClient

from cinema_platform.logging import service_logger

from .config import Settings

from .router.api import create_router, ReportInput, report_sentiments


def create_app(settings=None, *, engine=None, auth_transport=None, read_transport=None):
    settings = settings or Settings()
    own_engine = engine is None
    engine = engine or create_engine(settings.database_url, pool_pre_ping=True)
    logger = service_logger("review")

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(
            trust_env=False, transport=auth_transport
        ) as auth_http:
            with httpx.Client(
                trust_env=False, transport=read_transport, timeout=5
            ) as read_http:
                app.state.auth = AuthClient(
                    auth_http, settings.identity_origin, settings.service_key
                )
                app.state.read_http = read_http
                yield
        if own_engine:
            engine.dispose()

    app = FastAPI(
        title="Cinema Review",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.middleware("http")
    async def context(request, call_next):
        request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Service-Name"] = "review"
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
