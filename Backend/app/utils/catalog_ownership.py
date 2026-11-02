from fastapi import HTTPException
from app.core.config import settings
from app.utils.domain_ownership import domain_owner


def get_owner(db=None, *, lock=False):
    return domain_owner("catalog", settings.CATALOG_STORAGE_OWNER, db, lock=lock)


def require_legacy_catalog_owner(db=None):
    owner = get_owner(db, lock=db is not None)
    if owner != "monolith":
        raise HTTPException(410 if owner == "service" else 503, "Catalog đã chuyển hoặc đang chuyển dữ liệu")
