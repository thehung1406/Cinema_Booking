from contextlib import asynccontextmanager

from uuid import uuid4

import httpx

from fastapi import FastAPI

from fastapi.responses import JSONResponse

from sqlalchemy import create_engine

from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from cinema_platform.auth import AuthClient

from cinema_platform.logging import service_logger

from .config import Settings

from .clients import Clients

from .router.api import create_router, PERMISSIONS, MANAGEMENT, needed, operation_data


def create_app(settings=None, *, engine=None, auth_transport=None, read_transport=None):
    settings = settings or Settings()
    own_engine = engine is None
    engine = engine or create_engine(settings.database_url, pool_pre_ping=True)
    logger = service_logger("cinema")

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(
            trust_env=False, transport=auth_transport
        ) as auth_http:
            with httpx.Client(trust_env=False, transport=read_transport) as read_http:
                app.state.auth = AuthClient(
                    auth_http, settings.identity_origin, settings.service_key
                )
                app.state.clients = Clients(settings, read_http)
                yield
        if own_engine:
            engine.dispose()

    app = FastAPI(
        title="Cinema Service",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.engine = engine

    @app.middleware("http")
    async def context(request, call_next):
        response = await call_next(request)
        response.headers["X-Request-ID"] = str(uuid4())
        response.headers["X-Service-Name"] = "cinema"
        logger.info("method=%s status=%s", request.method, response.status_code)
        return response

    @app.exception_handler(SQLAlchemyError)
    async def db_error(request, exc):
        return JSONResponse(
            {"detail": "Dữ liệu thay đổi hoặc store Cinema chưa sẵn sàng"},
            status_code=409 if isinstance(exc, IntegrityError) else 503,
        )

    app.include_router(create_router(app, engine, settings, logger))
    return app


def application():
    return create_app()
