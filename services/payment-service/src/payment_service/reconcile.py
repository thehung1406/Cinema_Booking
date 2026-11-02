"""Recover lost acknowledgements without manufacturing provider success or refunds."""
from datetime import timedelta
from uuid import NAMESPACE_URL,uuid5
from sqlalchemy import select,func,or_
from cinema_platform.events import EventEnvelope,OutboxRecord
from cinema_platform.payment_contracts import BookingResult
from .models import Payment,Fulfillment,Case,now
from . import service,clients


def retry_capture(db,payment_id):
    row=db.get(OutboxRecord,str(uuid5(NAMESPACE_URL,f'payment:{payment_id}:PaymentCaptured.v1')))
    if row is None: return False
    row.status='PENDING'; row.attempts=0; row.available_at=now(); row.last_error=None
    return True


def tick(engine):
    from sqlmodel import Session
    from fastapi import HTTPException
    with Session(engine) as db:
        ids=list(db.scalars(select(Payment.id).outerjoin(Fulfillment).where(Payment.status=='PAID',or_(Fulfillment.payment_id.is_(None),Fulfillment.outcome=='PENDING'))))
    for payment_id in ids:
        result=None
        try: result=BookingResult.model_validate(clients.booking_call(f'/internal/v1/payment-results/{payment_id}'))
        except (HTTPException,ValueError): pass
        with Session(engine) as db,db.begin():
            payment=db.get(Payment,payment_id)
            if result:
                # The recovery envelope is stable across polling and has a distinct
                # identity from the broker envelope. A conflicting outcome is rejected.
                event=EventEnvelope(event_id=uuid5(NAMESPACE_URL,f'payment-result-poll:{payment_id}'),occurred_at=payment.paid_at,
                    event_type='PaymentBookingResult.v1',producer='booking',aggregate_id=f'payment:{payment_id}',aggregate_version=1,
                    correlation_id=f'booking:{payment.booking_id}',data=result.model_dump(mode='json'))
                service.receive_result(db,event)
            service.lock(db,payment.booking_id)
            fulfillment=db.get(Fulfillment,payment_id)
            if fulfillment and fulfillment.outcome in {'CONFIRMED','REJECTED'}: continue
            outbox=db.get(OutboxRecord,str(uuid5(NAMESPACE_URL,f'payment:{payment_id}:PaymentCaptured.v1')))
            if outbox and outbox.status=='BLOCKED': service.open_case(db,payment_id,'EVENT_BLOCKED')
            if payment.paid_at and payment.paid_at<=now()-timedelta(seconds=30):
                service.open_case(db,payment_id,'PAID_UNCONFIRMED')
                if outbox and outbox.status=='PUBLISHED' and outbox.published_at<=now()-timedelta(seconds=30): retry_capture(db,payment_id)
    with Session(engine) as db:
        return db.scalar(select(func.count()).select_from(Case).where(Case.status=='OPEN'))
