from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app.core.database import get_session
from app.models import User
from app.schemas.auth import (
    RegisterRequest,
    UserRead, AccessTokenResponse, RefreshTokenRequest
)
from app.services.auth_service import AuthService
from app.utils.dependencies import get_current_user, oauth2_scheme

router = APIRouter(prefix="/auth",tags=["Auth"])

@router.post("/register",response_model=UserRead)
def register(data: RegisterRequest,session: Session = Depends(get_session)):
    user = AuthService.register(session=session,data=data)
    return user

@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    access_token , refresh_token= AuthService.login(
        session=session,
        username=form_data.username,
        password=form_data.password
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/refresh", response_model=AccessTokenResponse)
def refresh_token(data: RefreshTokenRequest):
    new_access_token = AuthService.refresh_token(data.refresh_token)
    return AccessTokenResponse(access_token=new_access_token)

@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),
    access_token: str = Depends(oauth2_scheme),
):
    AuthService.logout(user_id=current_user.id, access_token=access_token)
    return {"success": True, "message": "Logged out successfully"}
