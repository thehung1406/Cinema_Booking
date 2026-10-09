from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.redis import redis_client
from app.core.database import get_session
from app.models import User
from app.repositories.auth_repo import AuthRepository
from app.models.access_control import Permission, RolePermission

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session)
):
    if redis_client.get(f"blacklist:{token}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked"
        )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )

    user = AuthRepository.get_user(
        session,
        int(payload.get("sub"))
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user

def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    session: Session = Depends(get_session)
) -> Optional[User]:
    if not token:
        return None

    if redis_client.get(f"blacklist:{token}"):
        return None

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        return None

    if payload.get("type") != "access":
        return None

    sub = payload.get("sub")
    if not sub:
        return None

    try:
        user_id = int(sub)
    except (ValueError, TypeError):
        return None

    return AuthRepository.get_user(session, user_id)

def require_permission(code: str):
    def dependency(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
        permitted = session.exec(select(Permission.id).join(RolePermission)
            .where(RolePermission.role_id == user.role_id, Permission.code == code)).first()
        if permitted is None:
            raise HTTPException(403, "Bạn không có quyền thực hiện chức năng này")
        return user
    return dependency


def require_staff(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return require_permission("reviews.moderate")(user=user, session=session)

