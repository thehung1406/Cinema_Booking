"""Scaffold a service with its own settings, DB/migrations, auth and health.

Refuses existing targets. Example: python scripts/dev/scaffold_service.py ai-service
"""

import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def scaffold(name: str, output: Path | None = None):
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-service", name):
        raise ValueError("Use a lowercase name ending in -service")
    target = (output or ROOT / "services" / name).resolve()
    if ROOT not in target.parents or target.exists():
        raise ValueError("Target must be new and inside this repository")
    package, prefix = name.replace("-", "_"), name.removesuffix("-service").replace("-", "_").upper()
    files = {
        "pyproject.toml": '''[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"
[project]
name = "cinema-__NAME__"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["cinema-platform==0.1.0", "fastapi==0.128.0", "starlette==0.50.0", "pydantic-settings==2.12.0", "alembic==1.17.2", "psycopg2-binary==2.9.9", "uvicorn==0.24.0"]
[tool.setuptools.packages.find]
where = ["src"]
''',
        "src/__PACKAGE__/__init__.py": '"""__NAME__ owns only its local data."""\n',
        "src/__PACKAGE__/config.py": '''from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    database_url: str
    identity_origin: str = "http://fastapi:8000"
    service_key: str = ""
    model_config = SettingsConfigDict(env_prefix="__PREFIX___", extra="ignore")
''',
        "src/__PACKAGE__/main.py": '''from contextlib import asynccontextmanager
from uuid import uuid4
import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from cinema_platform.auth import AuthClient
from cinema_platform.logging import service_logger
from .config import Settings

def create_app(settings=None, *, transport=None):
    settings = settings or Settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    logger = service_logger("__NAME__")
    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(trust_env=False, transport=transport) as client:
            app.state.auth = AuthClient(client, settings.identity_origin, settings.service_key)
            yield
        engine.dispose()
    app = FastAPI(lifespan=lifespan, title="__NAME__", docs_url=None, redoc_url=None)
    @app.middleware("http")
    async def context(request, call_next):
        request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info("service=__NAME__ method=%s status=%s request_id=%s", request.method, response.status_code, request_id)
        return response
    @app.get("/health/live")
    def live():
        return {"status": "ok", "service": "__NAME__"}
    @app.get("/health/ready")
    def ready():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return {"status": "ready", "service": "__NAME__"}
    return app

def application():
    return create_app()
''',
        "src/__PACKAGE__/auth.py": '''from fastapi import Header, HTTPException, Request
from cinema_platform.auth import AuthError
def require_permission(code):
    async def dependency(request: Request, authorization: str = Header(default="")):
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "Bearer token required")
        try:
            return await request.app.state.auth.introspect(token, code)
        except AuthError as exc:
            raise HTTPException(exc.status_code, "Operation is not authorized") from exc
    return dependency
''',
        "alembic.ini": '[alembic]\nscript_location = %(here)s/alembic\n',
        "alembic/env.py": '''from alembic import context
from sqlalchemy import create_engine
from cinema_platform.events import MessagingBase
from __PACKAGE__.config import Settings
with create_engine(Settings().database_url).connect() as connection:
    context.configure(connection=connection, target_metadata=MessagingBase.metadata)
    with context.begin_transaction():
        context.run_migrations()
''',
        "alembic/versions/001_messaging.py": '''from alembic import op
from cinema_platform import migrations_v1
revision = "001"
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    migrations_v1.create(op)
def downgrade():
    migrations_v1.drop(op)
''',
        "tests/test_health.py": '''from fastapi.testclient import TestClient
from __PACKAGE__.config import Settings
from __PACKAGE__.main import create_app
def test_health_uses_own_database():
    with TestClient(create_app(Settings(database_url="sqlite://"))) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
''',
        ".env.example": '__PREFIX___DATABASE_URL=postgresql+psycopg2://replace:replace@own-db:5432/cinema___PACKAGE__\n__PREFIX___IDENTITY_ORIGIN=http://fastapi:8000\n__PREFIX___SERVICE_KEY=\n',
        "Dockerfile": '''FROM python:3.11-slim
WORKDIR /app/service
COPY packages/python-platform /tmp/python-platform
RUN pip install --no-cache-dir /tmp/python-platform
COPY services/__NAME__/ /app/service/
RUN pip install --no-cache-dir .
CMD ["uvicorn", "__PACKAGE__.main:application", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]
''',
        "README.md": '# __NAME__\n\nOwn DB/credential, Alembic and image. Build context is repository root. Add domain models only here, not in cinema-platform.\n\nInstall cinema-platform then this project; set __PREFIX___DATABASE_URL, migrate with `alembic upgrade head`, then run the Docker command. Never use a shared domain ORM/session.\n',
    }
    # Keep generated migrations editable through Alembic's standard template.
    files["alembic/script.py.mako"] = (ROOT / "services/notification-service/alembic/script.py.mako").read_text(encoding="utf-8")
    for path, content in files.items():
        for token, value in {"__NAME__": name, "__PACKAGE__": package, "__PREFIX__": prefix}.items():
            path, content = path.replace(token, value), content.replace(token, value)
        file = target / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8", newline="\n")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    args = parser.parse_args()
    print(scaffold(args.name))
