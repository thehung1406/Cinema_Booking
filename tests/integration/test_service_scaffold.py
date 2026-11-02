import importlib
import os
from pathlib import Path
import runpy
import subprocess
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parents[2]


def test_scaffold_has_independent_migrations_health_and_refuses_overwrite():
    scaffold = runpy.run_path(str(ROOT / "scripts/dev/scaffold_service.py"))["scaffold"]
    target = ROOT / "tmp" / ("scaffold-" + uuid4().hex) / "migration-sample-service"
    scaffold("migration-sample-service", target)
    with pytest.raises(ValueError):
        scaffold("migration-sample-service", target)
    with pytest.raises(ValueError):
        scaffold("../escape-service")
    db_url = "sqlite:///" + str(target / "test.sqlite3")
    env = os.environ | {
        "PYTHONPATH": str(target / "src") + os.pathsep + os.environ.get("PYTHONPATH", ""),
        "MIGRATION_SAMPLE_DATABASE_URL": db_url,
    }
    command = [sys.executable, "-m", "alembic", "-c", str(target / "alembic.ini")]
    subprocess.run(command + ["upgrade", "head"], env=env, check=True, capture_output=True)
    engine = create_engine(db_url)
    assert "outbox_events" in inspect(engine).get_table_names()
    sys.path.insert(0, str(target / "src"))
    module = importlib.import_module("migration_sample_service.main")
    settings = importlib.import_module("migration_sample_service.config").Settings(database_url=db_url)
    with TestClient(module.create_app(settings)) as client:
        assert client.get("/health/ready").status_code == 200
        assert client.get("/health/live").headers["x-request-id"]
    subprocess.run(command + ["downgrade", "base"], env=env, check=True, capture_output=True)
    assert "outbox_events" not in inspect(engine).get_table_names()
    engine.dispose()
