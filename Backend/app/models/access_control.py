from typing import Optional
from sqlmodel import Field, SQLModel


class Role(SQLModel, table=True):
    __tablename__ = "roles"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(max_length=20, unique=True)
    name: str = Field(max_length=100)


class Permission(SQLModel, table=True):
    __tablename__ = "permissions"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(max_length=100, unique=True)
    name: str = Field(max_length=100)


class RolePermission(SQLModel, table=True):
    __tablename__ = "role_permissions"
    role_id: int = Field(primary_key=True, foreign_key="roles.id", ondelete="CASCADE")
    permission_id: int = Field(primary_key=True, foreign_key="permissions.id", ondelete="CASCADE")
