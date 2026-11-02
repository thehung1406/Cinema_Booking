from contextlib import asynccontextmanager
from datetime import timedelta
from secrets import compare_digest
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, select, delete, func, or_, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from cinema_platform.auth import Principal
from cinema_platform.logging import service_logger
from .config import Settings
from .models import User, Role, Permission, RolePermission, LoginSession, utcnow
from .schemas import (RegisterRequest, RefreshRequest, IntrospectionRequest, RoleAssignment,
    PermissionAssignment, ProfileRequest, EmployeeCreate, EmployeeWrite, AccountStatus)
from . import tokens

MANAGEMENT = {"films.manage", "rooms.manage", "showtimes.manage", "seat_types.manage",
              "users.manage", "roles.manage", "knowledge.manage", "reports.view"}


def profile(user):
    return dict(id=user.id, username=user.username, email=user.email, full_name=user.full_name,
                phone=user.phone, role=user.role)


def employee(user):
    return {**profile(user), "role_id": user.role_id, "is_active": user.is_active}


def permissions(db, user):
    return list(db.scalars(select(Permission.code).join(RolePermission)
        .where(RolePermission.role_id == user.role_id).order_by(Permission.code)))


def create_app(settings=None, *, engine=None):
    settings = settings or Settings()
    own_engine = engine is None
    engine = engine or create_engine(settings.database_url, pool_pre_ping=True)
    logger = service_logger("identity")

    @asynccontextmanager
    async def lifespan(app):
        yield
        if own_engine:
            engine.dispose()

    app = FastAPI(title="Cinema Identity", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def context(request, call_next):
        request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Service-Name"] = "identity"
        logger.info("method=%s status=%s request_id=%s", request.method, response.status_code, request_id)
        return response

    @app.exception_handler(SQLAlchemyError)
    async def storage_error(request, exc):
        return JSONResponse({"detail": "Identity storage unavailable"}, status_code=503)

    def database():
        with Session(engine) as db:
            yield db

    def writes():
        if not settings.writes_enabled:
            raise HTTPException(503, "Identity đang chuyển dữ liệu")

    def private(x_service_key: str = Header(default="")):
        if len(settings.service_key) < 32:
            raise HTTPException(503, "Service credential is not configured")
        if not compare_digest(x_service_key.encode(), settings.service_key.encode()):
            raise HTTPException(401, "Invalid service credential")

    def bearer(authorization: str = Header(default="")):
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token or len(token) > 8192:
            raise HTTPException(401, "Bearer token required")
        return token

    def current(token=Depends(bearer), db=Depends(database)):
        user, _ = tokens.validate(db, settings, token)
        return user

    def require(code):
        def check(user=Depends(current), db=Depends(database)):
            if code not in permissions(db, user):
                raise HTTPException(403, "Bạn không có quyền thực hiện chức năng này")
            return user
        return check

    def management(user=Depends(current), db=Depends(database)):
        if not MANAGEMENT.intersection(permissions(db, user)):
            raise HTTPException(403, "Bạn không có quyền truy cập trang quản trị")
        return user

    def get_user(db, user_id):
        user = db.scalar(select(User).where(User.id == user_id).with_for_update(of=User))
        if user is None:
            raise HTTPException(404, "Không tìm thấy tài khoản")
        return user

    def commit(db):
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Tài khoản hoặc email đã tồn tại") from None

    @app.get("/health/live")
    def live():
        return {"status": "ok", "service": "identity"}

    @app.get("/health/ready")
    def ready():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM login_sessions LIMIT 0"))
        except SQLAlchemyError:
            return JSONResponse({"status": "not_ready", "service": "identity"}, status_code=503)
        return {"status": "ready", "service": "identity"}

    @app.get("/internal/v1/migration/state", dependencies=[Depends(private)], include_in_schema=False)
    def migration_state():
        return {"writes_enabled": settings.writes_enabled}

    @app.post("/internal/v1/auth/introspect", response_model=Principal,
              dependencies=[Depends(private)], include_in_schema=False)
    def introspect(body: IntrospectionRequest, db=Depends(database)):
        user, _ = tokens.validate(db, settings, body.token)
        return Principal(user_id=user.id, role=user.role, is_active=user.is_active, permissions=permissions(db, user))

    @app.post("/internal/v1/auth/context", dependencies=[Depends(private)], include_in_schema=False)
    def auth_context(body: IntrospectionRequest, db=Depends(database)):
        user, _ = tokens.validate(db, settings, body.token)
        return {**employee(user), "permissions": permissions(db, user)}

    @app.post("/internal/v1/users/profiles", dependencies=[Depends(private)], include_in_schema=False)
    def profiles(body: ProfileRequest, db=Depends(database)):
        # Explicit allowlist: never expose password hashes, tokens or session data.
        return [profile(user) for user in db.scalars(select(User).where(User.id.in_(set(body.user_ids))))]

    @app.post("/auth/register", dependencies=[Depends(writes)])
    def register(body: RegisterRequest, db=Depends(database)):
        role = db.scalar(select(Role).where(Role.code == "USER"))
        if not role:
            raise HTTPException(503, "Default role is not configured")
        if db.scalar(select(User.id).where(or_(User.username == body.username, User.email == str(body.email)))):
            raise HTTPException(400, "Username or email already exists")
        user = User(**body.model_dump(exclude={"role_id", "password"}), role_id=role.id,
                    password=tokens.passwords.hash(body.password))
        db.add(user)
        commit(db)
        return profile(user)

    @app.post("/auth/login", dependencies=[Depends(writes)])
    def login(form: OAuth2PasswordRequestForm = Depends(), db=Depends(database)):
        user = db.scalar(select(User).where(User.username == form.username).with_for_update(of=User))
        if not user or not user.is_active or len(form.password.encode()) > 72:
            raise HTTPException(401, "Invalid username or password")
        try:
            valid = tokens.passwords.verify(form.password, user.password)
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise HTTPException(401, "Invalid username or password")
        result = tokens.login(db, settings, user)
        commit(db)
        return result

    @app.get("/auth/me")
    def me(user=Depends(current)):
        return profile(user)

    @app.post("/auth/refresh", dependencies=[Depends(writes)])
    def refresh(body: RefreshRequest, db=Depends(database)):
        user, session = tokens.validate(db, settings, body.refresh_token, "refresh", lock=True)
        # Existing frontend expects only a new access token; refresh remains valid until fixed expiry.
        result = tokens.mint(settings, user.id, session.id, "access", utcnow() + timedelta(minutes=settings.access_minutes))
        commit(db)
        return {"access_token": result, "token_type": "bearer"}

    @app.post("/auth/logout", dependencies=[Depends(writes)])
    def logout(token=Depends(bearer), db=Depends(database)):
        _, session = tokens.validate(db, settings, token, lock=True)
        session.revoked_at = utcnow()
        commit(db)
        return {"success": True, "message": "Logged out successfully"}

    @app.get("/admin/session")
    def admin_session(user=Depends(management), db=Depends(database)):
        return {"user": {k: v for k, v in profile(user).items() if k in {"id", "username", "full_name", "role"}},
                "permissions": permissions(db, user)}

    @app.get("/admin/employees")
    def employees(q: str = Query("", max_length=100), offset: int = Query(0, ge=0),
                  limit: int = Query(50, ge=1, le=200), user=Depends(require("users.manage")), db=Depends(database)):
        query = select(User)
        if q:
            query = query.where(or_(User.username.icontains(q, autoescape=True),
                User.full_name.icontains(q, autoescape=True), User.email.icontains(q, autoescape=True)))
        total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
        return {"items": [employee(u) for u in db.scalars(query.order_by(User.id.desc()).offset(offset).limit(limit)).unique()], "total": total}

    @app.post("/admin/employees", status_code=201, dependencies=[Depends(writes)])
    def create_employee(body: EmployeeCreate, user=Depends(require("users.manage")),
                        role_admin=Depends(require("roles.manage")), db=Depends(database)):
        role = db.get(Role, body.role_id)
        if not role:
            raise HTTPException(404, "Vai trò không tồn tại")
        if role.code == "USER":
            raise HTTPException(400, "Tài khoản nhân viên phải có vai trò nhân viên")
        row = User(**body.model_dump(exclude={"password"}), password=tokens.passwords.hash(body.password))
        db.add(row)
        commit(db)
        return employee(row)

    @app.put("/admin/employees/{user_id}", dependencies=[Depends(writes)])
    def update_employee(user_id: int, body: EmployeeWrite, user=Depends(require("users.manage")), db=Depends(database)):
        row = get_user(db, user_id)
        for key, value in body.model_dump().items():
            setattr(row, key, value)
        commit(db)
        return employee(row)

    @app.put("/admin/employees/{user_id}/status", dependencies=[Depends(writes)])
    def account_status(user_id: int, body: AccountStatus, user=Depends(require("users.manage")), db=Depends(database)):
        row = get_user(db, user_id)
        if row.id == user.id and not body.is_active:
            raise HTTPException(409, "Không thể tự khóa tài khoản đang đăng nhập")
        row.is_active = body.is_active
        if not body.is_active:
            db.execute(update(LoginSession).where(LoginSession.user_id == row.id,
                LoginSession.revoked_at.is_(None)).values(revoked_at=utcnow()))
        commit(db)
        return employee(row)

    @app.get("/access-control/roles")
    def roles(user=Depends(require("roles.manage")), db=Depends(database)):
        return [dict(id=r.id, code=r.code, name=r.name) for r in db.scalars(select(Role).order_by(Role.id))]

    @app.get("/access-control/permissions")
    def all_permissions(user=Depends(require("roles.manage")), db=Depends(database)):
        return [dict(id=p.id, code=p.code, name=p.name) for p in db.scalars(select(Permission).order_by(Permission.id))]

    @app.get("/access-control/roles/{role_id}/permissions")
    def role_permissions(role_id: int, user=Depends(require("roles.manage")), db=Depends(database)):
        return [dict(id=p.id, code=p.code, name=p.name) for p in db.scalars(select(Permission)
            .join(RolePermission).where(RolePermission.role_id == role_id))]

    @app.put("/access-control/users/{user_id}/role", dependencies=[Depends(writes)])
    def assign_role(user_id: int, body: RoleAssignment, user=Depends(require("roles.manage")), db=Depends(database)):
        row, role = get_user(db, user_id), db.get(Role, body.role_id)
        if not role:
            raise HTTPException(404, "Vai trò không tồn tại")
        if row.id == user.id and row.role_id != role.id:
            raise HTTPException(409, "Không thể tự thay đổi vai trò đang sử dụng")
        row.role_id = role.id
        commit(db)
        return {"user_id": row.id, "role_id": role.id, "role": role.code}

    @app.put("/access-control/roles/{role_id}/permissions", dependencies=[Depends(writes)])
    def assign_permissions(role_id: int, body: PermissionAssignment, user=Depends(require("roles.manage")), db=Depends(database)):
        if not db.get(Role, role_id):
            raise HTTPException(404, "Vai trò không tồn tại")
        if role_id == user.role_id:
            raise HTTPException(409, "Không thể sửa quyền của vai trò đang sử dụng")
        ids = set(body.permission_ids)
        if set(db.scalars(select(Permission.id).where(Permission.id.in_(ids)))) != ids:
            raise HTTPException(400, "Danh sách quyền không hợp lệ")
        db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        db.add_all([RolePermission(role_id=role_id, permission_id=i) for i in ids])
        commit(db)
        return {"role_id": role_id, "permission_ids": sorted(ids)}

    return app


def application():
    return create_app()
