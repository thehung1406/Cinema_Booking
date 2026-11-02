from fastapi import HTTPException
from app.core.config import settings
from app.utils.domain_ownership import domain_owner


def get_owner(db=None, *, lock=False):
    return domain_owner("review", settings.REVIEW_STORAGE_OWNER, db, lock=lock)


def require_legacy_review_owner(db=None):
    owner = get_owner(db, lock=db is not None)
    if owner != "monolith":
        raise HTTPException(503 if owner == "maintenance" else 410,
            "Review đang chuyển dữ liệu" if owner == "maintenance" else "Review đã chuyển service riêng; truy cập qua /api")


def require_legacy_review_route():
    require_legacy_review_owner()
