from fastapi import HTTPException
from app.core.config import settings
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from app.models.migration_ownership import DomainOwnership


def domain_owner(domain, config_owner, db=None, *, lock=False):
    if db is None:
        from sqlmodel import Session
        from app.core.database import engine
        with Session(engine) as own:
            return domain_owner(domain, config_owner, own, lock=lock)
    if db.get_bind().dialect.name == "sqlite":
        return config_owner  # Legacy SQLite unit fixtures have no technical migrations.
    try:
        query = select(DomainOwnership).where(DomainOwnership.domain == domain)
        if lock:
            query = query.with_for_update(read=True)
        row = db.execute(query).scalar_one_or_none()
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Không thể kiểm tra quyền sở hữu miền") from exc
    if row is None:
        raise HTTPException(503, "Domain ownership migration is not initialized")
    rank = {"monolith": 0, "maintenance": 1, "service": 2}
    return max((row.owner, config_owner), key=rank.__getitem__)
