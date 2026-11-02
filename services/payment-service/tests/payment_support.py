import os, sys
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "booking-service/tests"))
from booking_support import booking_store
from test_booking import ready


@pytest.fixture
def payment_store(monkeypatch):
    url = os.environ.get("PAYMENT_DATABASE_URL", "")
    if "test" not in url:
        pytest.skip("Isolated Payment PostgreSQL required")
    root = create_engine(url)
    schema = "payment_test_" + uuid4().hex
    with root.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    migration_url = make_url(url).update_query_dict(
        {"options": f"-csearch_path={schema},public"}
    )
    monkeypatch.setenv(
        "PAYMENT_DATABASE_URL", migration_url.render_as_string(hide_password=False)
    )
    engine = create_engine(migration_url)
    try:
        command.upgrade(
            Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head"
        )
        yield engine
    finally:
        engine.dispose()
        with root.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()
