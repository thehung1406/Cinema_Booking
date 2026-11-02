import os, sys, runpy
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

base = Path(__file__).resolve().parents[2]
for name in ["booking", "payment"]:
    sys.path.insert(0, str(base / (name + "-service") / "tests"))
from booking_support import booking_store
from test_booking import ready
from test_saga import pair

payment_store = runpy.run_path(str(base / "payment-service/tests/conftest.py"))[
    "payment_store"
]


@pytest.fixture
def reporting_store(monkeypatch):
    url = os.environ.get("REPORTING_DATABASE_URL", "")
    if "test" not in url:
        pytest.skip("Isolated Reporting DB required")
    root = create_engine(url)
    schema = "report_test_" + uuid4().hex
    with root.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = make_url(url).update_query_dict({"options": f"-csearch_path={schema},public"})
    monkeypatch.setenv(
        "REPORTING_DATABASE_URL", url.render_as_string(hide_password=False)
    )
    engine = create_engine(url)
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
