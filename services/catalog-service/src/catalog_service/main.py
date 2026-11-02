from contextlib import asynccontextmanager

from uuid import uuid4

import httpx

from fastapi import FastAPI

from fastapi.responses import JSONResponse

from sqlalchemy import create_engine

from sqlalchemy.exc import SQLAlchemyError

from cinema_platform.auth import AuthClient

from cinema_platform.logging import service_logger

from .config import Settings

from .router.api import create_router, MANAGEMENT


def create_app(settings=None, *, engine=None, auth_transport=None):
    settings = settings or Settings()
    own_engine = engine is None
    engine = engine or create_engine(settings.database_url, pool_pre_ping=True)
    logger = service_logger("catalog")

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(trust_env=False, transport=auth_transport) as http:
            app.state.auth = AuthClient(
                http, settings.identity_origin, settings.service_key
            )
            yield
        if own_engine:
            engine.dispose()

    app = FastAPI(
        title="Cinema Catalog",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.exception_handler(SQLAlchemyError)
    async def storage_error(request, exc):
        return JSONResponse({"detail": "Catalog storage unavailable"}, status_code=503)

    @app.middleware("http")
    async def context(request, call_next):
        response = await call_next(request)
        response.headers["X-Request-ID"] = str(uuid4())
        response.headers["X-Service-Name"] = "catalog"
        logger.info("method=%s status=%s", request.method, response.status_code)
        return response

    app.include_router(create_router(app, engine, settings, logger))
    return app


def application():
    return create_app()
