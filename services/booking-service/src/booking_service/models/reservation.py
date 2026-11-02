from datetime import datetime,timezone
from typing import Optional
from sqlmodel import Field
from sqlalchemy import Column,DateTime,JSON,Numeric,Index,CheckConstraint,text
from decimal import Decimal
from .base import Model

class Reservation(Model,table=True):
    __tablename__='reservations'
    __table_args__=(Index('uq_active_user_show_reservation','user_id','showtime_id',unique=True,postgresql_where=text("status IN ('ACTIVE','CHECKOUT')")),
        CheckConstraint("status IN ('ACTIVE','CHECKOUT','CONFIRMED','EXPIRED','RELEASED')",name='ck_reservation_status'))
    id:str=Field(primary_key=True,max_length=36)
    user_id:int=Field(index=True)
    showtime_id:int=Field(index=True)
    sales_version:int
    seat_ids:list[int]=Field(default_factory=list,sa_column=Column(JSON,nullable=False))
    status:str=Field(default='ACTIVE',max_length=20)
    expires_at:datetime=Field(sa_column=Column(DateTime(timezone=True),nullable=False))
    created_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc),sa_column=Column(DateTime(timezone=True),nullable=False))

class Checkout(Model,table=True):
    __tablename__='checkout_snapshots'
    booking_id:int=Field(primary_key=True,foreign_key='bookings.id',ondelete='RESTRICT')
    booking_version:int=Field(default=1)
    reservation_id:str=Field(foreign_key='reservations.id',max_length=36)
    amount:Decimal=Field(sa_column=Column(Numeric(12,2),nullable=False))
    currency:str=Field(default='VND',max_length=3)
    deadline:datetime=Field(sa_column=Column(DateTime(timezone=True),nullable=False))
    digest:str=Field(max_length=64)
    snapshot:dict=Field(sa_column=Column(JSON,nullable=False))

class Idempotency(Model,table=True):
    __tablename__='booking_idempotency'
    user_id:int=Field(primary_key=True)
    key:str=Field(primary_key=True,max_length=128)
    request_hash:str=Field(max_length=64)
    booking_id:int=Field(foreign_key='bookings.id',ondelete='RESTRICT')
    response:dict=Field(sa_column=Column(JSON,nullable=False))
