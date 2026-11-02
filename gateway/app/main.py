"""Stage M1: /api proxies to the existing backend; authorization stays there."""

from contextlib import asynccontextmanager
import logging
from time import perf_counter
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from .config import GatewaySettings
from .proxy import proxy_request

logger = logging.getLogger("cinema.gateway")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s cinema.gateway %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False
METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


def create_app(settings: GatewaySettings | None = None, *, transport=None) -> FastAPI:
    settings = settings or GatewaySettings()

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(
            timeout=settings.timeout(),
            limits=httpx.Limits(max_connections=settings.max_connections),
            transport=transport, trust_env=False, follow_redirects=False,
        ) as client:
            app.state.upstream = client
            yield

    app = FastAPI(title="Cinema Booking Gateway", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = str(uuid4())
        started = perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        # Deliberately omit URL/query/headers: callbacks and ticket paths contain sensitive values.
        logger.info(
            "method=%s upstream=%s status=%s duration_ms=%.1f request_id=%s",
            request.method, getattr(request.state, "upstream_domain", "gateway"), response.status_code, (perf_counter() - started) * 1000,
            request.state.request_id,
        )
        return response

    @app.get("/health/live")
    async def live():
        return {"status": "ok", "service": "gateway"}

    @app.get("/health/ready")
    async def ready():
        try:
            upstream = await app.state.upstream.get(settings.monolith_url + "/")
            if upstream.is_success:
                for domain in settings.required_domains:
                    health = await app.state.upstream.get(settings.origin_for(domain) + "/health/ready")
                    if not health.is_success:
                        return JSONResponse({"status": "not_ready", "upstream": domain}, status_code=503)
                return {"status": "ready", "upstream": "monolith"}
        except httpx.RequestError:
            pass
        return JSONResponse({"status": "not_ready", "upstream": "monolith"}, status_code=503)

    @app.api_route("/api", methods=METHODS)
    @app.api_route("/api/{path:path}", methods=METHODS)
    async def forward(request: Request):
        if request.method == "GET" and request.url.path == "/api/admin/catalog" and "catalog" in settings.enabled_domains:
            from .aggregation import admin_catalog
            return await admin_catalog(request, settings)
        return await proxy_request(request, settings)

    return app


app = create_app()
