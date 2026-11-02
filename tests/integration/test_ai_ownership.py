"""Persistent ownership survives config rollback and waits for in-flight writers."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.migration_ownership import DomainOwnership, OwnershipAudit, OwnershipBase
from app.utils.ai_ownership import require_legacy_ai_owner
from app.worker.ai_ownership import set_owner


@pytest.fixture
def ownership_store():
    url = os.environ.get("TEST_POSTGRES_URL", "")
    if "test" not in url:
        pytest.skip("Dedicated test database required")
    root = create_engine(url)
    schema = "ownership_test_" + uuid4().hex
    with root.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        OwnershipBase.metadata.create_all(engine)
        with Session(engine) as db, db.begin():
            db.add(DomainOwnership(domain="ai", owner="monolith"))
        yield engine
    finally:
        engine.dispose()
        with root.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()


def test_persisted_fence_blocks_old_writer_even_with_default_config(ownership_store, monkeypatch):
    monkeypatch.setattr(settings, "AI_STORAGE_OWNER", "monolith")
    with Session(ownership_store) as db:
        require_legacy_ai_owner(db)
        db.commit()
        with pytest.raises(ValueError):
            set_owner(db, "service", "Must freeze first")
        db.rollback()
        for owner, code in [("maintenance", 503), ("service", 410)]:
            set_owner(db, owner, "Test audited cutover")
            db.commit()
            with pytest.raises(HTTPException) as blocked:
                require_legacy_ai_owner(db)
            assert blocked.value.status_code == code
            db.rollback()
        with pytest.raises(ValueError):
            set_owner(db, "monolith", "Unsafe rollback")
        db.rollback()
        assert len(db.scalars(select(OwnershipAudit)).all()) == 2


def test_freeze_waits_for_existing_writer_transaction(ownership_store, monkeypatch):
    monkeypatch.setattr(settings, "AI_STORAGE_OWNER", "monolith")
    entered, completed = Event(), Event()
    def freeze():
        with Session(ownership_store) as db, db.begin():
            entered.set()
            set_owner(db, "maintenance", "Wait for in-flight write")
        completed.set()
    with ThreadPoolExecutor(max_workers=1) as pool, Session(ownership_store) as writer:
        require_legacy_ai_owner(writer)
        job = pool.submit(freeze)
        assert entered.wait(5)
        assert not completed.wait(0.2)
        writer.commit()
        job.result(timeout=5)
        assert completed.is_set()


def test_missing_ownership_row_fails_closed(ownership_store, monkeypatch):
    monkeypatch.setattr(settings, "AI_STORAGE_OWNER", "monolith")
    with Session(ownership_store) as db:
        db.execute(text("DELETE FROM domain_ownership"))
        db.commit()
        with pytest.raises(HTTPException) as blocked:
            require_legacy_ai_owner(db)
        assert blocked.value.status_code == 503
