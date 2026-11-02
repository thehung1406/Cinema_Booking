from test_ai_ownership import ownership_store  # noqa: F401
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.migration_ownership import DomainOwnership
from app.utils.review_ownership import require_legacy_review_owner
from app.worker.ai_ownership import set_owner


def test_review_fence_survives_env_rollback_independently_of_ai(ownership_store, monkeypatch):
    monkeypatch.setattr(settings, "REVIEW_STORAGE_OWNER", "monolith")
    monkeypatch.setattr(settings, "AI_STORAGE_OWNER", "service")
    with Session(ownership_store) as db:
        db.get(DomainOwnership, "ai").owner = "service"
        db.add(DomainOwnership(domain="review", owner="monolith"))
        db.commit()
        require_legacy_review_owner(db)
        db.commit()
        for owner, status in [("maintenance", 503), ("service", 410)]:
            set_owner(db, owner, "Review cutover audit", domain="review")
            db.commit()
            with pytest.raises(HTTPException) as blocked:
                require_legacy_review_owner(db)
            assert blocked.value.status_code == status
            db.rollback()
        with pytest.raises(ValueError):
            set_owner(db, "monolith", "Unsafe Review rollback", domain="review")
