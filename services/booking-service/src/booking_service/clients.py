from types import SimpleNamespace
import httpx
from fastapi import HTTPException
from .config import settings

def call(origin,method,path,**kwargs):
    if len(settings.service_key)<32: raise HTTPException(503,'Internal service credential not configured')
    try:
        with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as http:
            response=http.request(method,origin+path,headers={'X-Service-Key':settings.service_key},**kwargs)
        if response.status_code!=200: raise HTTPException(503,'Dịch vụ phụ thuộc chưa sẵn sàng')
        return response.json()
    except (httpx.RequestError,ValueError) as exc: raise HTTPException(503,'Dịch vụ phụ thuộc chưa sẵn sàng') from exc

def contact(user_id):
    rows=call(settings.identity_origin,'POST','/internal/v1/users/profiles',json={'user_ids':[user_id]})
    if len(rows)!=1 or rows[0].get('id')!=user_id or not rows[0].get('email'): raise HTTPException(503,'Thiếu thông tin khách hàng')
    return SimpleNamespace(**rows[0])
