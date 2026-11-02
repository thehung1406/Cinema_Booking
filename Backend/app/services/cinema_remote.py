"""Cinema metadata adapters; selling decisions use Booking-owned publications."""
from types import SimpleNamespace
import httpx
from fastapi import HTTPException
from app.core.config import settings


def call(method,path,**kwargs):
    if len(settings.INTERNAL_SERVICE_KEY)<32: raise HTTPException(503,"Cinema credential is not configured")
    try:
        with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as client:
            response=client.request(method,settings.CINEMA_SERVICE_ORIGIN+path,headers={"X-Service-Key":settings.INTERNAL_SERVICE_KEY},**kwargs)
        if response.status_code==404: raise HTTPException(404,"Không tìm thấy dữ liệu Cinema")
        if response.status_code!=200: raise HTTPException(503,"Cinema unavailable")
        return response.json()
    except (httpx.RequestError,ValueError) as exc: raise HTTPException(503,"Cinema unavailable") from exc


def object_at(path):
    try:
        row=call("GET",path)
        if not isinstance(row,dict) or not isinstance(row.get("id"),int) or row["id"]<=0: raise ValueError("Invalid Cinema entity")
        return SimpleNamespace(**row)
    except (ValueError,TypeError) as exc: raise HTTPException(503,"Invalid Cinema entity") from exc
