from datetime import datetime,timezone
from decimal import Decimal
from sqlalchemy import Integer,String,Numeric,DateTime,JSON,ForeignKey,ForeignKeyConstraint,UniqueConstraint,CheckConstraint
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column

def now(): return datetime.now(timezone.utc)
class Base(DeclarativeBase): pass

class Checkout(Base):
    __tablename__='payment_checkouts'
    booking_id:Mapped[int]=mapped_column(Integer,primary_key=True)
    booking_version:Mapped[int]=mapped_column(Integer,primary_key=True)
    reservation_id:Mapped[str]=mapped_column(String(36))
    user_id:Mapped[int]=mapped_column(Integer,index=True)
    amount:Mapped[Decimal]=mapped_column(Numeric(12,2))
    currency:Mapped[str]=mapped_column(String(3))
    deadline:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    digest:Mapped[str]=mapped_column(String(64))
    payment_method:Mapped[str]=mapped_column(String(50))
    booking_date:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    primary_payment_id:Mapped[int|None]=mapped_column(Integer)

class Payment(Base):
    __tablename__='payments'
    __table_args__=(UniqueConstraint('provider','transaction_ref',name='uq_payment_provider_transaction'),
        CheckConstraint('amount>0',name='ck_payment_amount_positive'),
        CheckConstraint("status IN ('PENDING','PAID','FAILED','CANCELLED')",name='ck_payment_status'),
        ForeignKeyConstraint(['booking_id','checkout_version'],['payment_checkouts.booking_id','payment_checkouts.booking_version']))
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    booking_id:Mapped[int]=mapped_column(Integer,index=True)
    provider:Mapped[str]=mapped_column(String(30))
    payment_method:Mapped[str]=mapped_column(String(50))
    merchant_ref:Mapped[str]=mapped_column(String(100),unique=True)
    transaction_ref:Mapped[str|None]=mapped_column(String(100))
    amount:Mapped[Decimal]=mapped_column(Numeric(12,2))
    currency:Mapped[str]=mapped_column(String(3),default='VND')
    status:Mapped[str]=mapped_column(String(20),default='PENDING')
    paid_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    checkout_version:Mapped[int]=mapped_column(Integer,default=1)

class ProviderResult(Base):
    __tablename__='provider_results'
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    payment_id:Mapped[int]=mapped_column(ForeignKey('payments.id'),index=True)
    amount:Mapped[Decimal]=mapped_column(Numeric(14,2))
    transaction_ref:Mapped[str]=mapped_column(String(100))
    response_code:Mapped[str]=mapped_column(String(20))
    transaction_status:Mapped[str]=mapped_column(String(20))
    success:Mapped[bool]
    origin:Mapped[str]=mapped_column(String(30),default='SIGNED_CALLBACK')
    received_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Fulfillment(Base):
    __tablename__='payment_fulfillments'
    payment_id:Mapped[int]=mapped_column(ForeignKey('payments.id'),primary_key=True)
    outcome:Mapped[str]=mapped_column(String(20),default='PENDING')
    reason:Mapped[str]=mapped_column(String(100),default='AWAITING_BOOKING')
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Case(Base):
    __tablename__='payment_reconciliation'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    payment_id:Mapped[int]=mapped_column(ForeignKey('payments.id'),index=True)
    reason:Mapped[str]=mapped_column(String(100))
    reference:Mapped[str]=mapped_column(String(150),default='')
    status:Mapped[str]=mapped_column(String(20),default='OPEN',index=True)
    detail:Mapped[dict]=mapped_column(JSON,default=dict)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(UniqueConstraint('payment_id','reason','reference'),)
