from datetime import timedelta, timezone
from hashlib import sha256
from secrets import compare_digest
from uuid import uuid4
from fastapi import HTTPException
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from .models import User, LoginSession, utcnow

passwords = CryptContext(schemes=["bcrypt"], deprecated="auto")


def digest(token):
    return sha256(token.encode()).hexdigest()


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def mint(settings, user_id, session_id, kind, expiry):
    now = utcnow()
    return jwt.encode(dict(sub=str(user_id), sid=session_id, jti=str(uuid4()), type=kind,
        iss=settings.issuer, aud=settings.audience, iat=now, nbf=now, exp=expiry),
        settings.signing_keys[settings.current_kid], algorithm="HS256", headers={"kid": settings.current_kid})


def decode(settings, token, kind):
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "HS256" or header.get("kid") not in settings.signing_keys:
            raise ValueError("Unknown signing key")
        claims = jwt.decode(token, settings.signing_keys[header["kid"]], algorithms=["HS256"],
            issuer=settings.issuer, audience=settings.audience,
            options={"require_exp": True, "require_sub": True, "require_iat": True,
                     "require_nbf": True, "require_iss": True, "require_aud": True, "require_jti": True})
        if claims.get("type") != kind or not isinstance(claims.get("sid"), str) or int(claims["sub"]) <= 0:
            raise ValueError("Invalid token claims")
        return claims
    except (JWTError, ValueError, TypeError, KeyError):
        raise HTTPException(401, "Invalid or expired token") from None


def validate(db, settings, token, kind="access", *, lock=False):
    claims = decode(settings, token, kind)
    query = select(LoginSession).where(LoginSession.id == claims["sid"])
    if lock:
        query = query.with_for_update()
    session = db.scalar(query)
    if not session or session.user_id != int(claims["sub"]) or session.revoked_at or aware(session.expires_at) <= utcnow():
        raise HTTPException(401, "Session expired or revoked")
    if kind == "refresh" and not compare_digest(session.refresh_digest, digest(token)):
        raise HTTPException(401, "Refresh token revoked")
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(403, "Tài khoản đã bị khóa")
    return user, session


def login(db, settings, user):
    now = utcnow()
    sid = str(uuid4())
    expires = now + timedelta(days=settings.refresh_days)
    refresh = mint(settings, user.id, sid, "refresh", expires)
    db.add(LoginSession(id=sid, user_id=user.id, refresh_digest=digest(refresh), expires_at=expires))
    return dict(access_token=mint(settings, user.id, sid, "access", now + timedelta(minutes=settings.access_minutes)),
                refresh_token=refresh, token_type="bearer")
