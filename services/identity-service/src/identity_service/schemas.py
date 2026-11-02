from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class AdminInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class EmployeeWrite(AdminInput):
    full_name: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=100)
    phone: str | None = Field(default=None, max_length=15)


class EmployeeCreate(EmployeeWrite):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=72)
    role_id: int = Field(gt=0)

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Mật khẩu không được vượt quá 72 byte")
        return value


class AccountStatus(AdminInput):
    is_active: bool



class RegisterRequest(EmployeeCreate):
    # Public input cannot choose a role; the endpoint assigns USER.
    role_id: None = None

class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=1, max_length=8192)

class IntrospectionRequest(BaseModel):
    token: str = Field(min_length=1, max_length=8192)

class RoleAssignment(AdminInput):
    role_id: int = Field(gt=0)

class PermissionAssignment(AdminInput):
    permission_ids: list[int] = Field(max_length=200)

class ProfileRequest(BaseModel):
    user_ids: list[int] = Field(max_length=100)
