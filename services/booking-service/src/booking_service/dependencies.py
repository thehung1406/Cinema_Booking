from secrets import compare_digest
from fastapi import Depends,Header,HTTPException,Request
from sqlmodel import Session
from cinema_platform.auth import Principal,AuthError

class User(Principal):
    @property
    def id(self): return self.user_id

def get_session(request:Request):
    with Session(request.app.state.engine) as db: yield db

async def get_current_user(request:Request,authorization:str=Header(default='')):
    scheme,_,token=authorization.partition(' ')
    if scheme.lower()!='bearer' or not token: raise HTTPException(401,'Bearer token required')
    try: return User.model_validate((await request.app.state.auth.introspect(token)).model_dump())
    except AuthError as exc: raise HTTPException(exc.status_code,'Không thể xác thực Booking') from exc

async def get_optional_current_user(request:Request,authorization:str=Header(default='')):
    if not authorization: return None
    try: return await get_current_user(request,authorization)
    except HTTPException as exc:
        if exc.status_code in {401,403}: return None
        raise

def require_permission(permission):
    def check(user=Depends(get_current_user)):
        if permission not in user.permissions: raise HTTPException(403,'Bạn không có quyền thực hiện chức năng này')
        return user
    return check

require_staff=require_permission('reviews.moderate')

def writes(request:Request):
    if not request.app.state.settings.writes_enabled: raise HTTPException(503,'Booking đang chuyển dữ liệu')

def private(request:Request,x_service_key:str=Header(default='')):
    key=request.app.state.settings.service_key
    if len(key)<32: raise HTTPException(503,'Credential is not configured')
    if not compare_digest(key.encode(),x_service_key.encode()): raise HTTPException(401,'Invalid service credential')
