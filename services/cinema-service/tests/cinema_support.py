import os
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


@pytest.fixture
def cinema_store(monkeypatch):
    url=os.environ.get("CINEMA_DATABASE_URL", "")
    if "test" not in url: pytest.skip("Isolated Cinema PostgreSQL required")
    root=create_engine(url)
    schema="cinema_test_"+uuid4().hex
    with root.begin() as conn: conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine=create_engine(url,connect_args={"options":f"-csearch_path={schema},public"})
    # Run the actual frozen migration, including capacity, overlap and immutability guards.
    from sqlalchemy.engine import make_url
    migration_url=make_url(url).update_query_dict({"options":f"-csearch_path={schema},public"})
    monkeypatch.setenv("CINEMA_DATABASE_URL",migration_url.render_as_string(hide_password=False))
    config=Config(str(Path(__file__).resolve().parents[1]/"alembic.ini"))
    try:
        command.upgrade(config,"head")
        yield engine
    finally:
        engine.dispose()
        with root.begin() as conn: conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()
