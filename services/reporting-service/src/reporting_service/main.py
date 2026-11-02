from contextlib import asynccontextmanager

import httpx

from fastapi import FastAPI

from fastapi.responses import JSONResponse

from sqlalchemy import create_engine

from sqlalchemy.exc import SQLAlchemyError

from cinema_platform.auth import AuthClient

from .config import Settings

from .router.api import create_router, Filters


def create_app(settings=None, *, engine=None, auth_transport=None):
    cfg = settings or Settings()
    owned = engine is None
    engine = engine or create_engine(cfg.database_url, pool_pre_ping=True)

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(trust_env=False, transport=auth_transport) as http:
            app.state.auth = AuthClient(http, cfg.identity_origin, cfg.service_key)
            yield
        if owned:
            engine.dispose()

    app = FastAPI(
        title="Reporting Service",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.engine = engine
    app.state.settings = cfg

    @app.middleware("http")
    async def context(request, call_next):
        response = await call_next(request)
        response.headers["X-Service-Name"] = "reporting"
        return response

    @app.exception_handler(SQLAlchemyError)
    async def unavailable(request, exc):
        return JSONResponse(
            {"detail": "Dữ liệu báo cáo chưa sẵn sàng"}, status_code=503
        )

    app.include_router(create_router(app, engine, cfg))
    return app


def application():
    return create_app()
