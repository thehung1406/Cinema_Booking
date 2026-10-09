from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, select
from sqlalchemy import delete
from app.core.database import get_session
from app.models import User, Role, Permission, RolePermission
from app.utils.dependencies import require_permission

router = APIRouter(prefix="/access-control", tags=["Access Control"])


class RoleAssignment(SQLModel):
    role_id: int


class PermissionAssignment(SQLModel):
    permission_ids: list[int]


@router.get("/roles")
def roles(db: Session = Depends(get_session), admin=Depends(require_permission("roles.manage"))):
    return db.exec(select(Role).order_by(Role.id)).all()


@router.get("/permissions")
def permissions(db: Session = Depends(get_session), admin=Depends(require_permission("roles.manage"))):
    return db.exec(select(Permission).order_by(Permission.id)).all()


@router.get("/roles/{role_id}/permissions")
def role_permissions(role_id: int, db: Session = Depends(get_session), admin=Depends(require_permission("roles.manage"))):
    return db.exec(select(Permission).join(RolePermission).where(RolePermission.role_id == role_id)).all()


@router.put("/users/{user_id}/role")
def assign_role(user_id: int, body: RoleAssignment, db: Session = Depends(get_session),
                admin=Depends(require_permission("users.manage"))):
    user, role = db.get(User, user_id), db.get(Role, body.role_id)
    if not user or not role:
        raise HTTPException(404, "Người dùng hoặc vai trò không tồn tại")
    user.role_id = role.id
    db.add(user)
    db.commit()
    return {"user_id": user.id, "role_id": role.id, "role": role.code}


@router.put("/roles/{role_id}/permissions")
def assign_permissions(role_id: int, body: PermissionAssignment, db: Session = Depends(get_session),
                       admin=Depends(require_permission("roles.manage"))):
    if not db.get(Role, role_id):
        raise HTTPException(404, "Vai trò không tồn tại")
    ids = set(body.permission_ids)
    known = set(db.exec(select(Permission.id).where(Permission.id.in_(ids))).all()) if ids else set()
    if known != ids:
        raise HTTPException(400, "Danh sách quyền không hợp lệ")
    db.exec(delete(RolePermission).where(RolePermission.role_id == role_id))
    db.add_all([RolePermission(role_id=role_id, permission_id=permission_id) for permission_id in ids])
    db.commit()
    return {"role_id": role_id, "permission_ids": sorted(ids)}
