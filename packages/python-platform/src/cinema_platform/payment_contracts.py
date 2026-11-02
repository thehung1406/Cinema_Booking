from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,AwareDatetime

class CheckoutFact(BaseModel):
    model_config=ConfigDict(extra='ignore')
    booking_id:int=Field(gt=0)
    booking_version:int=Field(gt=0)
    reservation_id:UUID
    amount:Decimal=Field(gt=0,max_digits=12,decimal_places=2)
    currency:Literal['VND']
    deadline:AwareDatetime
    digest:str=Field(pattern='^[a-f0-9]{64}$')
    user_id:int=Field(gt=0)
    payment_method:str
    booking_date:AwareDatetime
    booking_status:str
    payment_status:str

class Captured(BaseModel):
    model_config=ConfigDict(extra='forbid')
    payment_id:int=Field(gt=0)
    booking_id:int=Field(gt=0)
    booking_version:int=Field(gt=0)
    reservation_id:UUID
    checkout_digest:str=Field(pattern='^[a-f0-9]{64}$')
    amount:Decimal=Field(gt=0,max_digits=14,decimal_places=2)
    currency:Literal['VND']
    transaction_ref:str=Field(min_length=1,max_length=100)
    collected_at:AwareDatetime

class BookingResult(BaseModel):
    model_config=ConfigDict(extra='forbid')
    payment_id:int=Field(gt=0)
    booking_id:int=Field(gt=0)
    booking_version:int=Field(gt=0)
    reservation_id:UUID
    checkout_digest:str=Field(pattern='^[a-f0-9]{64}$')
    outcome:Literal['CONFIRMED','REJECTED']
    reason:str=Field(max_length=100)

class CheckoutChanged(BaseModel):
    model_config=ConfigDict(extra='forbid')
    booking_id:int=Field(gt=0)
    booking_version:int=Field(gt=0)
    reservation_id:UUID
    amount:Decimal=Field(gt=0,max_digits=12,decimal_places=2)
    currency:Literal['VND']
    deadline:AwareDatetime
    showtime_id:int=Field(gt=0)
    sales_version:int=Field(gt=0)
