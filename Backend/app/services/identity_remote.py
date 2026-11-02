"""Typed, uncached Identity access. No signing keys or fallback to archived accounts."""
import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from app.core.config import settings


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(gt=0)
    username: str
    email: str
    full_name: str | None
    phone: str | None
    role: str


class UserContext(Profile):
    role_id: int = Field(gt=0)
    is_active: bool
    permissions: list[str]


def call(path, body):
    if len(settings.INTERNAL_SERVICE_KEY) < 32:
        raise HTTPException(503, "Identity service credential is not configured")
    try:
        with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
            response = client.post(settings.IDENTITY_SERVICE_ORIGIN + path,
                headers={"X-Service-Key": settings.INTERNAL_SERVICE_KEY}, json=body)
        if response.status_code in {401, 403}:
            raise HTTPException(response.status_code, "Identity rejected access")
        if response.status_code != 200:
            raise HTTPException(503, "Identity unavailable")
        return response.json()
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(503, "Identity unavailable") from exc


def context(token):
    try:
        user = UserContext.model_validate(call("/internal/v1/auth/context", {"token": token}))
    except ValidationError as exc:
        raise HTTPException(503, "Invalid Identity response") from exc
    if not user.is_active:
        raise HTTPException(403, "Tài khoản đã bị khóa")
    return user


def profiles(user_ids):
    if not user_ids:
        return {}
    try:
        items = [Profile.model_validate(row) for row in call("/internal/v1/users/profiles", {"user_ids": sorted(set(user_ids))})]
        if len({p.id for p in items}) != len(items) or any(p.id not in user_ids for p in items):
            raise ValueError("Unexpected profiles")
        return {p.id: p for p in items}
    except (ValidationError, TypeError, ValueError) as exc:
        raise HTTPException(503, "Invalid Identity profile response") from exc


def contact(db, user_id):
    from app.utils.identity_ownership import get_owner
    owner = get_owner(db)
    if owner == "maintenance":
        raise HTTPException(503, "Identity đang chuyển dữ liệu")
    if owner == "service":
        user = profiles([user_id]).get(user_id)
    else:
        from app.models import User
        user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Không tìm thấy tài khoản")
    return user
