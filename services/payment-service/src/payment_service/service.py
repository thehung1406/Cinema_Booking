from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from uuid import uuid4,uuid5,NAMESPACE_URL
import hashlib,json
from fastapi import HTTPException
from sqlalchemy import select,text
from cinema_platform.events import EventEnvelope,OutboxRecord
from cinema_platform.outbox import enqueue
from cinema_platform.payment_contracts import Captured,BookingResult
from cinema_platform.consume import once
from .models import Checkout,Payment,ProviderResult,Fulfillment,Case,now
from .config import settings

def lock(db,booking_id): db.execute(text('SELECT pg_advisory_xact_lock(8812,:id)'),{'id':booking_id})

def register(db,fact):
    lock(db,fact.booking_id)
    row=db.get(Checkout,(fact.booking_id,fact.booking_version))
    values=dict(reservation_id=str(fact.reservation_id),user_id=fact.user_id,amount=fact.amount,currency=fact.currency,deadline=fact.deadline,digest=fact.digest,payment_method=fact.payment_method,booking_date=fact.booking_date)
    if row:
        if any(getattr(row,k)!=v for k,v in values.items()): raise ValueError('Immutable checkout changed')
    else:
        row=Checkout(booking_id=fact.booking_id,booking_version=fact.booking_version,**values); db.add(row); db.flush()
    return row

def open_case(db,payment_id,reason,reference='',detail=None):
    case_id=str(uuid5(NAMESPACE_URL,f'payment-case:{payment_id}:{reason}:{reference}'))
    row=db.get(Case,case_id)
    if row is None:
        row=Case(id=case_id,payment_id=payment_id,reason=reason,reference=reference,detail=detail or {})
        db.add(row)
    elif row.status!='OPEN': row.status='OPEN'; row.updated_at=now()
    return row

def attempt(db,fact,user_id):
    if fact.user_id!=user_id: raise HTTPException(403,'Bạn không có quyền thanh toán đơn này')
    row=register(db,fact)
    if fact.booking_status!='PENDING' or fact.payment_status not in {'PENDING','FAILED'} or fact.deadline<=now(): raise HTTPException(409,'Checkout đã hết hạn hoặc không còn chờ thanh toán')
    if db.scalar(select(Payment.id).where(Payment.booking_id==fact.booking_id,Payment.status=='PAID')): raise HTTPException(409,'Đã thu tiền; đang xác nhận vé hoặc cần đối soát')
    payment=db.scalar(select(Payment).where(Payment.booking_id==fact.booking_id,Payment.checkout_version==fact.booking_version,Payment.status=='PENDING').order_by(Payment.id))
    if payment is None:
        payment=Payment(booking_id=fact.booking_id,checkout_version=fact.booking_version,provider='VNPAY',payment_method='VNPAY',merchant_ref=uuid4().hex,amount=fact.amount,currency=fact.currency)
        db.add(payment); db.flush()
    db.commit(); return payment

def capture_event(db,payment,checkout,amount):
    data=Captured(payment_id=payment.id,booking_id=payment.booking_id,booking_version=payment.checkout_version,reservation_id=checkout.reservation_id,checkout_digest=checkout.digest,amount=amount,currency=payment.currency,transaction_ref=payment.transaction_ref,collected_at=payment.paid_at)
    event=EventEnvelope(event_id=uuid5(NAMESPACE_URL,f'payment:{payment.id}:PaymentCaptured.v1'),event_type='PaymentCaptured.v1',producer='payment',aggregate_id=f'payment:{payment.id}',aggregate_version=1,correlation_id=f'booking:{payment.booking_id}',data=data.model_dump(mode='json'))
    if db.get(OutboxRecord,str(event.event_id)) is None: enqueue(db,event,'public')

def record(db,params):
    payment=db.scalar(select(Payment).where(Payment.merchant_ref==params.get('vnp_TxnRef')))
    if payment is None: raise HTTPException(404,'Giao dịch không tồn tại')
    lock(db,payment.booking_id)
    db.refresh(payment)
    if params.get('vnp_TmnCode')!=settings.tmn_code: raise HTTPException(400,'Merchant không khớp')
    try:
        raw=str(params['vnp_Amount'])
        if not raw.isascii() or not raw.isdigit() or len(raw)>14: raise ValueError()
        amount=Decimal(int(raw))/100
        if amount<=0: raise ValueError()
    except (KeyError,ValueError,InvalidOperation): raise HTTPException(400,'Số tiền provider không hợp lệ')
    success=params.get('vnp_ResponseCode')=='00' and params.get('vnp_TransactionStatus',params.get('vnp_ResponseCode'))=='00'
    txn=str(params.get('vnp_TransactionNo') or '0')
    if len(txn)>100 or (success and txn=='0'): raise HTTPException(400,'Thiếu tham chiếu provider')
    material=dict(payment_id=payment.id,amount=str(amount),transaction_ref=txn,response_code=str(params.get('vnp_ResponseCode',''))[:20],transaction_status=str(params.get('vnp_TransactionStatus',params.get('vnp_ResponseCode','')))[:20],success=success)
    receipt_id=hashlib.sha256(json.dumps(material,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    repeated=db.get(ProviderResult,receipt_id) is not None
    if repeated: return payment,True,amount!=payment.amount
    db.add(ProviderResult(id=receipt_id,**material)); db.flush()
    checkout=db.get(Checkout,(payment.booking_id,payment.checkout_version))
    if success:
        if payment.status=='PAID':
            if payment.transaction_ref!=txn or amount!=payment.amount: open_case(db,payment.id,'ADDITIONAL_COLLECTION',txn,{'amount':str(amount)})
        else:
            other=db.scalar(select(Payment).where(Payment.provider=='VNPAY',Payment.transaction_ref==txn,Payment.id!=payment.id))
            if other:
                # Preserve this receipt and PAID outcome without breaking the unique
                # provider transaction reference on the primary financial ledger.
                payment.status='PAID'; payment.paid_at=now()
                open_case(db,payment.id,'PROVIDER_REFERENCE_CONFLICT',txn)
                db.add(Fulfillment(payment_id=payment.id,outcome='REJECTED',reason='PROVIDER_REFERENCE_CONFLICT'))
            else:
                payment.status='PAID'; payment.transaction_ref=txn; payment.paid_at=now()
                if amount!=payment.amount: open_case(db,payment.id,'AMOUNT_MISMATCH',txn,{'expected':str(payment.amount),'collected':str(amount)})
                if checkout.primary_payment_id is None: checkout.primary_payment_id=payment.id
                elif checkout.primary_payment_id!=payment.id: open_case(db,payment.id,'DUPLICATE_PAYMENT',str(checkout.primary_payment_id))
                db.add(Fulfillment(payment_id=payment.id,outcome='PENDING',reason='AWAITING_BOOKING'))
                capture_event(db,payment,checkout,amount)
    elif payment.status!='PAID': payment.status='FAILED'
    payment.updated_at=now(); db.flush()
    return payment,False,amount!=payment.amount

def receive_result(db,event):
    if event.event_type!='PaymentBookingResult.v1' or event.producer!='booking' or event.aggregate_version!=1: raise ValueError('Unsupported Booking result')
    result=BookingResult.model_validate(event.data)
    if event.aggregate_id!=f'payment:{result.payment_id}': raise ValueError('Wrong result aggregate')
    def apply():
        payment=db.get(Payment,result.payment_id)
        if payment is None: raise ValueError('Unknown payment result')
        lock(db,payment.booking_id)
        checkout=db.get(Checkout,(payment.booking_id,payment.checkout_version))
        if payment.status!='PAID' or result.booking_id!=payment.booking_id or result.booking_version!=payment.checkout_version or str(result.reservation_id)!=checkout.reservation_id or result.checkout_digest!=checkout.digest: raise ValueError('Result checkout mismatch')
        row=db.get(Fulfillment,payment.id)
        if row is None: row=Fulfillment(payment_id=payment.id); db.add(row)
        if row.outcome in {'CONFIRMED','REJECTED'} and (row.outcome,row.reason)!=(result.outcome,result.reason): raise ValueError('Conflicting Booking outcome')
        row.outcome=result.outcome; row.reason=result.reason; row.updated_at=now()
        if result.outcome=='REJECTED': open_case(db,payment.id,'BOOKING_REJECTED',result.reason)
        for case in db.scalars(select(Case).where(Case.payment_id==payment.id,Case.reason.in_(['PAID_UNCONFIRMED','EVENT_BLOCKED']))): case.status='RESOLVED'; case.updated_at=now()
    return once(db,'payment.booking.v1',event,apply)

def view(db,booking_id,user_id=None):
    checkout=db.scalar(select(Checkout).where(Checkout.booking_id==booking_id).order_by(Checkout.booking_version.desc()))
    if checkout is None: return None
    if user_id is not None and checkout.user_id!=user_id: raise HTTPException(403,'Bạn không có quyền xem giao dịch')
    payments=list(db.scalars(select(Payment).where(Payment.booking_id==booking_id).order_by(Payment.id)))
    paid=[p for p in payments if p.status=='PAID']
    confirmed=any((row:=db.get(Fulfillment,p.id)) and row.outcome=='CONFIRMED' for p in paid)
    review=any(db.scalar(select(Case.id).where(Case.payment_id==p.id,Case.status=='OPEN')) for p in paid)
    rejected=any((row:=db.get(Fulfillment,p.id)) and row.outcome=='REJECTED' for p in paid)
    stage='ISSUED' if confirmed else 'REQUIRES_REVIEW' if review or rejected else 'PROCESSING' if paid else 'FAILED' if payments and all(p.status in {'FAILED','CANCELLED'} for p in payments) else 'AWAITING_PAYMENT'
    provider='PAID' if paid else 'FAILED' if stage=='FAILED' else 'PENDING'
    return dict(booking_id=booking_id,payment_status=provider,provider_status=provider,fulfillment_status=stage,requires_review=review or rejected,total_amount=str(checkout.amount),currency=checkout.currency,booking_date=checkout.booking_date,payment_method=checkout.payment_method,booking_status='CONFIRMED' if confirmed else None,can_retry=not paid and checkout.deadline>now())
