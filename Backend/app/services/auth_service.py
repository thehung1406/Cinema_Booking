from datetime import datetime
from jose import jwt, JWTError
from app.core.config import settings

from sqlmodel import Session
from fastapi import HTTPException, status
from app.utils.enum import UserRole
from app.models.user import User
from app.repositories.auth_repo import AuthRepository
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token
)
from app.core.redis import redis_client

class AuthService:

    @staticmethod
    def register(session: Session,data) -> User:
        if AuthRepository.get_user_by_username(session, data.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        if AuthRepository.get_user_by_email(session, data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
        new_user = User(
            username=data.username,
            password=hash_password(data.password),
            email=data.email,
            phone =data.phone,
            full_name=data.full_name,
            role=UserRole.USER,
            created_at=datetime.now(),
        )
        return AuthRepository.create_user(session, new_user)

    @staticmethod
    def login(session: Session, username: str, password: str):
        user = AuthRepository.get_user_by_username(session, username)
        if not user or not verify_password(password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        payload = {
            "sub": str(user.id),
            "role": user.role,
        }
        access_token = create_access_token(payload)
        refresh_token = create_refresh_token(payload)
        redis_client.setex(
            f"refresh_token:{user.id}",
            60 * 60 * 24 * 30,
            refresh_token
        )
        return access_token, refresh_token

    @staticmethod
    def refresh_token(refresh_token: str) -> str:
        try:
            payload = jwt.decode(
                refresh_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token type"
            )

        user_id = payload.get("sub")

        redis_token = redis_client.get(f"refresh_token:{user_id}")
        if redis_token != refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired or revoked"
            )

        return create_access_token({
            "sub": user_id,
            "role": payload.get("role")
        })


    @staticmethod
    def logout(user_id: int,access_token: str):
        redis_client.delete(f"refresh_token:{user_id}")

        payload = jwt.decode(
            access_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        exp = payload.get("exp")
        ttl = exp - int(datetime.utcnow().timestamp())

        if ttl > 0:
            redis_client.setex(f"blacklist:{access_token}",ttl,"1")
