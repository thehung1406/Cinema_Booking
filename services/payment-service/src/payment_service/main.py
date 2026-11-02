from contextlib import asynccontextmanager

import httpx

from fastapi import FastAPI

from fastapi.responses import JSONResponse

from sqlalchemy import create_engine

from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from cinema_platform.auth import AuthClient

from .config import Settings, request_settings

from .router.api import create_router


def create_app(settings=None, *, engine=None, auth_transport=None):
    settings = settings or Settings()
    owned = engine is None
    engine = engine or create_engine(settings.database_url, pool_pre_ping=True)

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(trust_env=False, transport=auth_transport) as http:
            app.state.auth = AuthClient(
                http, settings.identity_origin, settings.service_key
            )
            yield
        if owned:
            engine.dispose()

    app = FastAPI(
        title="Payment Service",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.engine = engine
    app.state.settings = settings

    @app.middleware("http")
    async def context(request, call_next):
        token = request_settings.set(settings)
        try:
            response = await call_next(request)
            response.headers["X-Service-Name"] = "payment"
            return response
        finally:
            request_settings.reset(token)

    @app.exception_handler(SQLAlchemyError)
    async def db_error(request, exc):
        return JSONResponse(
            {"detail": "Payment chưa sẵn sàng; thử lại cùng giao dịch"},
            status_code=409 if isinstance(exc, IntegrityError) else 503,
        )

    app.include_router(create_router(app, engine, settings))
    return app


def application():
    return create_app()
