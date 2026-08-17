from typing import Optional
from pydantic import BaseModel, EmailStr

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: EmailStr # Dùng để tự động validate định dạng email
    full_name: str
    phone: Optional[str]

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    phone: Optional[str]
    role: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
