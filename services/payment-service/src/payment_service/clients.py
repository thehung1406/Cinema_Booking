import httpx
from fastapi import HTTPException
from cinema_platform.payment_contracts import CheckoutFact
from .config import settings

def booking_call(path):
    if len(settings.service_key)<32: raise HTTPException(503,'Payment credential not configured')
    try:
        with httpx.Client(timeout=5,trust_env=False) as http:
            response=http.get(settings.booking_origin+path,headers={'X-Service-Key':settings.service_key},follow_redirects=False)
        if response.status_code==404: raise HTTPException(404,'Không có checkout/kết quả xác nhận')
        if response.status_code!=200: raise HTTPException(503,'Booking chưa sẵn sàng')
        return response.json()
    except (httpx.RequestError,ValueError) as exc: raise HTTPException(503,'Booking chưa sẵn sàng') from exc

def checkout(booking_id):
    try:
        item=CheckoutFact.model_validate(booking_call(f'/internal/v1/checkouts/{booking_id}'))
        if item.booking_id!=booking_id: raise ValueError('Wrong checkout')
        return item
    except ValueError as exc: raise HTTPException(503,'Checkout contract không hợp lệ') from exc
