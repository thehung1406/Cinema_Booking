"""Private identity adapter during migration; never exposed through gateway."""

from secrets import compare_digest

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.models import Permission, RolePermission
from app.utils.dependencies import get_current_user
from cinema_platform.auth import Principal

router = APIRouter(prefix="/internal/v1/auth", include_in_schema=False)


def internal_service(x_service_key: str = Header(default="")):
    if len(settings.INTERNAL_SERVICE_KEY) < 32:
        raise HTTPException(503, "Internal identity adapter is not configured")
    if not compare_digest(x_service_key.encode(), settings.INTERNAL_SERVICE_KEY.encode()):
        raise HTTPException(401, "Invalid service credential")


class IntrospectionRequest(BaseModel):
    token: str = Field(min_length=1, max_length=8192)


@router.post("/introspect", response_model=Principal, dependencies=[Depends(internal_service)])
def introspect(body: IntrospectionRequest, db: Session = Depends(get_session)):
    # Reuse blacklist, token type/expiry, active-account and subject validation.
    try:
        user = get_current_user(token=body.token, session=db)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise HTTPException(401, "Unknown token subject") from exc
        raise
    if hasattr(user, "permissions"):
        return Principal(user_id=user.id, role=user.role, is_active=user.is_active, permissions=user.permissions)
    permissions = db.exec(select(Permission.code).join(RolePermission)
        .where(RolePermission.role_id == user.role_id).order_by(Permission.code)).all()
    return Principal(user_id=user.id, role=user.role, is_active=user.is_active, permissions=permissions)


@router.get("/ownership", dependencies=[Depends(internal_service)])
def ownership():
    from app.utils.identity_ownership import get_owner
    return {"owner": get_owner()}
