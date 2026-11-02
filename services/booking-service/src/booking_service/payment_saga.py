from uuid import NAMESPACE_URL,uuid5
from sqlalchemy import select
from sqlmodel import select as model_select
from cinema_platform.events import EventEnvelope
from cinema_platform.outbox import enqueue
from cinema_platform.consume import once
from cinema_platform.payment_contracts import Captured,BookingResult
from .models import BookingDetail,Reservation
from .models.payment_saga import PaymentReceipt
from .booking_repo import BookingRepository
from .checkout import require_checkout
from .reservations import rows,now
from .tickets import TicketService
from .events import booking_confirmed
from .payment_ownership import owner

def receive(db,event):
    if owner(db)!='service': raise RuntimeError('Booking payment consumer is frozen')
    if event.event_type!='PaymentCaptured.v1' or event.producer!='payment' or event.aggregate_version!=1: raise ValueError('Unsupported payment event')
    data=Captured.model_validate(event.data)
    if event.aggregate_id!=f'payment:{data.payment_id}': raise ValueError('Wrong payment aggregate')
    def apply():
        booking=BookingRepository.get_booking_by_id(db,data.booking_id,for_update=True)
        if booking is None: raise ValueError('Unknown booking for capture')
        old=db.get(PaymentReceipt,data.payment_id)
        if old:
            if old.booking_id!=data.booking_id or old.amount!=data.amount or any(old.result[k]!=v for k,v in dict(booking_version=data.booking_version,reservation_id=str(data.reservation_id),checkout_digest=data.checkout_digest).items()): raise ValueError('Payment ID reused')
            return
        checkout=require_checkout(db,booking)
        reason=''
        if data.booking_version!=checkout.booking_version or str(data.reservation_id)!=checkout.reservation_id or data.checkout_digest!=checkout.digest: reason='CHECKOUT_MISMATCH'
        elif data.amount!=checkout.amount or data.currency!=checkout.currency: reason='AMOUNT_MISMATCH'
        accepted=db.scalar(select(PaymentReceipt).where(PaymentReceipt.booking_id==booking.id,PaymentReceipt.outcome=='CONFIRMED'))
        if not reason and accepted: reason='DUPLICATE_PAYMENT'
        if not reason and (booking.booking_status in {'EXPIRED','CANCELLED'} or checkout.deadline<=now()): reason='RESERVATION_EXPIRED'
        reservation=db.get(Reservation,booking.reservation_id)
        details=list(db.exec(model_select(BookingDetail).where(BookingDetail.booking_id==booking.id).order_by(BookingDetail.seat_id)))
        held=rows(db,booking.showtime_id,[d.seat_id for d in details])
        if not reason and (reservation is None or reservation.status!='CHECKOUT' or len(held)!=len(details) or any(s.status!='HOLD' or s.reservation_id!=reservation.id or s.sales_version!=booking.sales_version or s.hold_by_user_id!=booking.user_id or s.hold_expired_at<=now() for s in held)): reason='HOLD_UNAVAILABLE'
        outcome='REJECTED' if reason else 'CONFIRMED'
        # PAID describes collected funds even when ticket confirmation is rejected.
        # Never downgrade a previously accepted order because a second payment arrived.
        booking.payment_status='PAID'
        if not reason:
            for seat in held:
                seat.status='BOOKED'; seat.hold_by_user_id=None; seat.hold_expired_at=None; seat.version+=1; seat.updated_at=now()
            booking.booking_status='CONFIRMED'; reservation.status='CONFIRMED'
            db.flush(); TicketService.issue_for_booking(db,booking)
            booking_confirmed(db,booking,data.payment_id)
        elif not accepted and booking.booking_status=='PENDING':
            booking.booking_status='EXPIRED' if checkout.deadline<=now() else 'CANCELLED'
            # Release only this reservation, without any payment/foreign ORM import.
            for seat in held:
                if seat.status=='HOLD' and seat.reservation_id==booking.reservation_id:
                    seat.status='AVAILABLE'; seat.hold_by_user_id=None; seat.hold_expired_at=None; seat.version+=1
            if reservation and reservation.status in {'ACTIVE','CHECKOUT'}: reservation.status='EXPIRED' if checkout.deadline<=now() else 'RELEASED'
        result=BookingResult(payment_id=data.payment_id,booking_id=booking.id,booking_version=data.booking_version,reservation_id=data.reservation_id,checkout_digest=data.checkout_digest,outcome=outcome,reason=reason or 'TICKETS_ISSUED')
        payload=result.model_dump(mode='json')
        db.add(PaymentReceipt(payment_id=data.payment_id,booking_id=booking.id,booking_version=data.booking_version,amount=data.amount,outcome=outcome,reason=result.reason,result=payload))
        enqueue(db,EventEnvelope(event_id=uuid5(NAMESPACE_URL,f'payment:{data.payment_id}:PaymentBookingResult.v1'),event_type='PaymentBookingResult.v1',producer='booking',aggregate_id=f'payment:{data.payment_id}',aggregate_version=1,correlation_id=f'booking:{booking.id}',data=payload),'public')
    return once(db,'booking.payment.v1',event,apply)
