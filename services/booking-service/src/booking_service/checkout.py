import hashlib,json
from datetime import datetime,timezone,timedelta
from fastapi import HTTPException
from .models import Checkout,BookingDetail
from .history import booking_detail

def digest(body): return hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def deadline(booking): return booking.expires_at or booking.booking_date+timedelta(minutes=10)

def create_checkout(db,booking):
    facts=booking_detail(db,booking)
    payload=dict(booking_id=booking.id,booking_version=booking.booking_version,reservation_id=booking.reservation_id,
        user_id=booking.user_id,showtime_id=booking.showtime_id,sales_version=booking.sales_version,
        amount=str(booking.total_amount),currency=booking.currency,deadline=deadline(booking).isoformat(),
        film=booking.catalog_film_snapshot,seats=[{**s,'price':str(s['price'])} for s in facts['seats']],
        food_items=json.loads(json.dumps(facts['foodItems'],default=str)),customer=dict(full_name=booking.customer_full_name,email=booking.customer_email,phone=booking.customer_phone))
    checkout=Checkout(booking_id=booking.id,booking_version=booking.booking_version,reservation_id=booking.reservation_id,amount=booking.total_amount,currency=booking.currency,deadline=deadline(booking),digest=digest(payload),snapshot=payload)
    db.add(checkout); db.flush(); return checkout

def require_checkout(db,booking):
    row=db.get(Checkout,booking.id)
    if row is None or row.digest!=digest(row.snapshot) or row.booking_version!=booking.booking_version or row.amount!=booking.total_amount or row.currency!=booking.currency or row.deadline!=deadline(booking) or row.reservation_id!=booking.reservation_id:
        raise HTTPException(409,'Checkout snapshot không khớp đơn')
    return row
