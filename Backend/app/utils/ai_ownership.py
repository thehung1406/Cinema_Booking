from app.core.config import settings
from app.utils.domain_ownership import domain_owner
from fastapi import HTTPException

def get_owner(db=None, *, lock=False):
    return domain_owner("ai", settings.AI_STORAGE_OWNER, db, lock=lock)

def require_legacy_ai_owner(db=None):
    owner = get_owner(db, lock=db is not None)
    if owner != "monolith":
        raise HTTPException(
            503 if owner == "maintenance" else 410,
            "AI đang chuyển dữ liệu" if owner == "maintenance" else "AI đã chuyển sang service riêng; truy cập qua /api",
        )


def require_legacy_ai_route():
    require_legacy_ai_owner()
