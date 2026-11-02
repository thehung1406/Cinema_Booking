from datetime import datetime,timezone
from decimal import Decimal
from sqlalchemy import Integer,String,Numeric,JSON,DateTime,Index,text
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column

class SagaBase(DeclarativeBase): pass
class PaymentOwnership(SagaBase):
    __tablename__='payment_ownership'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    owner:Mapped[str]=mapped_column(String(20))
class PaymentReceipt(SagaBase):
    __tablename__='booking_payment_receipts'
    payment_id:Mapped[int]=mapped_column(Integer,primary_key=True)
    booking_id:Mapped[int]=mapped_column(Integer,index=True)
    booking_version:Mapped[int]=mapped_column(Integer)
    amount:Mapped[Decimal]=mapped_column(Numeric(14,2))
    outcome:Mapped[str]=mapped_column(String(20))
    reason:Mapped[str]=mapped_column(String(100))
    result:Mapped[dict]=mapped_column(JSON)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    __table_args__=(Index('uq_booking_accepted_payment','booking_id','booking_version',unique=True,postgresql_where=text("outcome='CONFIRMED'")),)
