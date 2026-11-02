"""Own inbox and reconciliation only; no merchant signing key or Booking DB access."""
import threading,time
from sqlalchemy import create_engine,select
from cinema_platform.consume import consume_queue,once
from cinema_platform.logging import service_logger
from cinema_platform.payment_contracts import CheckoutChanged
from fastapi import HTTPException
from .config import Settings
from .models import Payment
from . import clients,service,reconcile


def receive(db,event):
    if event.event_type=='PaymentBookingResult.v1': return service.receive_result(db,event)
    if event.producer!='booking' or event.event_type not in {'CheckoutCreated.v1','BookingExpired.v1'}: raise ValueError('Unsupported checkout event')
    data=CheckoutChanged.model_validate(event.data)
    bid,version=data.booking_id,data.booking_version
    if event.aggregate_id!=f'booking:{bid}' or event.aggregate_version!=version: raise ValueError('Invalid checkout aggregate')
    # No transaction/lock has been acquired when fetching an authoritative fact.
    try: fact=clients.checkout(bid)
    except HTTPException as exc:
        if exc.status_code==404: raise ValueError('Unknown checkout event') from exc
        raise
    if fact.booking_version!=version or fact.reservation_id!=data.reservation_id or fact.amount!=data.amount or fact.currency!=data.currency or fact.deadline!=data.deadline: raise ValueError('Checkout event mismatch')
    if event.event_type=='BookingExpired.v1' and fact.booking_status!='EXPIRED': raise ValueError('Booking has not expired')
    def apply():
        service.register(db,fact)
        if event.event_type=='BookingExpired.v1':
            for payment in db.scalars(select(Payment).where(Payment.booking_id==bid,Payment.status=='PENDING')): payment.status='CANCELLED'
    return once(db,'payment.booking.v1',event,apply)


def main():
    settings=Settings(); engine=create_engine(settings.database_url,pool_pre_ping=True); log=service_logger('payment-worker')
    if not settings.writes_enabled: raise RuntimeError('Payment worker is frozen')
    def consume():
        while True:
            try: consume_queue(engine,settings.amqp_consumer_url,'payment.booking.v1',receive)
            except Exception as exc: log.warning('consumer deferred type=%s',type(exc).__name__); time.sleep(5)
    threading.Thread(target=consume,daemon=True).start()
    previous=None
    while True:
        try:
            count=reconcile.tick(engine)
            if count!=previous: log.warning('reconciliation open_cases=%s',count); previous=count
        except Exception as exc: log.warning('reconciliation deferred type=%s',type(exc).__name__)
        time.sleep(settings.reconcile_seconds)

if __name__=='__main__': main()
