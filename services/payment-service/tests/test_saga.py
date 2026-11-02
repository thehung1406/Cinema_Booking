from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import hashlib,hmac,urllib.parse,time,os
import httpx,pika,pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select,text,func
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session
from cinema_platform.events import EventEnvelope,OutboxRecord,InboxRecord,ReplayAudit
from cinema_platform.outbox import relay_one
from cinema_platform.broker import Publisher,connect
from cinema_platform.payment_contracts import CheckoutFact
from booking_service.config import Settings as BookingSettings,settings as booking_settings
from booking_service.main import create_app as booking_app
from booking_service import bookings,reservations,payment_saga
from booking_service.models import Booking,Ticket,SeatStatus,Payment as LegacyPayment
from booking_service.models.payment_saga import PaymentReceipt
from test_booking import request
from payment_service.config import Settings,settings
from payment_service.main import create_app
from payment_service.models import Payment,Checkout,ProviderResult,Fulfillment,Case,now
from payment_service import clients,service,reconcile

KEY='isolated-internal-service-key-32-characters-test-only'
AUTH={'Authorization':'Bearer isolated-token'}

@pytest.fixture
def pair(ready,payment_store,monkeypatch):
    state=dict(user_id=1,role='USER',is_active=True,permissions=[])
    with ready.begin() as conn: conn.execute(text("UPDATE payment_ownership SET owner='service'"))
    ba=booking_app(BookingSettings(service_key=KEY,writes_enabled=True),engine=ready,auth_transport=httpx.MockTransport(lambda r:httpx.Response(200,json=state)))
    cfg=Settings(service_key=KEY,writes_enabled=True,tmn_code='isolated-test-merchant',hash_secret='isolated-test-payment-key')
    pa=create_app(cfg,engine=payment_store,auth_transport=httpx.MockTransport(lambda r:httpx.Response(200,json=state)))
    with TestClient(ba) as bc,TestClient(pa) as pc:
        def call(path):
            res=bc.get(path,headers={'X-Service-Key':KEY})
            if res.status_code!=200: raise HTTPException(res.status_code,'Booking unavailable')
            return res.json()
        monkeypatch.setattr(clients,'booking_call',call)
        yield SimpleNamespace(book=ready,pay=payment_store,bc=bc,pc=pc,state=state,cfg=cfg)


def new_order(pair,ids=(1,2),key=None):
    with Session(pair.book) as db:
        rid=reservations.hold(db,1,list(ids),1)[0]['reservation_id']
        return bookings.create(db,request(ids=ids,reservation=rid,total=75000*len(ids)),1,key or uuid4().hex)['bookingId']


def start(pair,bid):
    res=pair.pc.post('/payment/vnpay-url',headers=AUTH,json={'bookingId':bid,'totalAmount':1})
    assert res.status_code==200,res.text
    params=dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(res.json()['paymentUrl']).query))
    return params


def signed(pair,params,**changes):
    body={k:v for k,v in params.items() if k in {'vnp_TxnRef','vnp_TmnCode','vnp_Amount'}}
    body.update(vnp_ResponseCode='00',vnp_TransactionStatus='00',vnp_TransactionNo=uuid4().hex)
    body.update(changes)
    raw='&'.join(f'{k}={urllib.parse.quote_plus(str(v))}' for k,v in sorted(body.items()))
    body['vnp_SecureHash']=hmac.new(pair.cfg.hash_secret.encode(),raw.encode(),hashlib.sha512).hexdigest()
    return body


def capture(pair,bid,**changes):
    body=signed(pair,start(pair,bid),**changes)
    result=pair.pc.get('/payment/vnpay-ipn',params=body)
    assert result.json()['RspCode'] in {'00','04'},result.text
    return body


def event_from(engine,kind):
    with Session(engine) as db:
        row=db.scalar(select(OutboxRecord).where(OutboxRecord.event_type==kind).order_by(OutboxRecord.created_at.desc()))
        return EventEnvelope.model_validate(row.payload)


def deliver(pair,event=None):
    with Session(pair.book) as db,db.begin(): payment_saga.receive(db,event or event_from(pair.pay,'PaymentCaptured.v1'))
    result=event_from(pair.book,'PaymentBookingResult.v1')
    with Session(pair.pay) as db,db.begin(): service.receive_result(db,result)
    return result


@pytest.mark.parametrize('first',['return','ipn'])
def test_signed_callback_orders_duplicates_and_lost_response(pair,first):
    bid=new_order(pair); url=start(pair,bid)
    assert url['vnp_Amount']=='15000000'
    assert start(pair,bid)['vnp_TxnRef']==url['vnp_TxnRef']
    body=signed(pair,url)
    route='/payment/vnpay-'+first
    assert pair.pc.post(route,json=body).status_code==200
    # Provider commit is independent of Booking/broker. Retry after a lost HTTP response.
    assert pair.pc.post('/payment/vnpay-return',json=body).json()['fulfillment_status']=='PROCESSING'
    assert pair.pc.get('/payment/vnpay-ipn',params=body).json()['RspCode']=='02'
    with Session(pair.book) as db: assert not list(db.scalars(select(Ticket)))
    event=event_from(pair.pay,'PaymentCaptured.v1'); result=deliver(pair,event)
    for _ in range(2):
        with Session(pair.book) as db,db.begin(): assert payment_saga.receive(db,event) is False
        with Session(pair.pay) as db,db.begin(): assert service.receive_result(db,result) is False
    response=pair.pc.post('/payment/vnpay-return',json=body).json()
    assert response['fulfillment_status']=='ISSUED' and response['status']=='success' and response['booking'] is None
    with Session(pair.book) as db:
        assert len(list(db.scalars(select(Ticket))))==2
        assert db.get(Booking,bid).booking_status=='CONFIRMED'
        assert db.scalar(select(func.count()).select_from(LegacyPayment))==0
        assert len(list(db.scalars(select(PaymentReceipt))))==1
        assert len(list(db.scalars(select(OutboxRecord).where(OutboxRecord.event_type=='BookingConfirmationEmailRequested.v1'))))==1
    with Session(pair.pay) as db:
        assert len(list(db.scalars(select(ProviderResult))))==1 and db.scalar(select(Payment)).status=='PAID'
        assert len(list(db.scalars(select(OutboxRecord))))==1


def test_bad_signature_merchant_amount_and_callback_reordering(pair):
    bid=new_order(pair); url=start(pair,bid)
    valid=signed(pair,url); invalid={**valid,'vnp_Amount':'100'}
    assert pair.pc.post('/payment/vnpay-return',json=invalid).status_code==400
    assert pair.pc.post('/payment/vnpay-ipn',json=invalid).json()['RspCode']=='97'
    assert pair.pc.post('/payment/vnpay-return',json=signed(pair,url,vnp_TmnCode='other')).status_code==400
    assert pair.pc.get('/payment/vnpay-return',params=[*valid.items(),('vnp_Amount','1')]).status_code==400
    with Session(pair.pay) as db: assert db.scalar(select(func.count()).select_from(ProviderResult))==0
    wrong=signed(pair,url,vnp_Amount='15000001')
    assert pair.pc.post('/payment/vnpay-ipn',json=wrong).json()['RspCode']=='04'
    result=deliver(pair)
    assert result.data['reason']=='AMOUNT_MISMATCH'
    failed=signed(pair,url,vnp_ResponseCode='24',vnp_TransactionStatus='02')
    pair.pc.post('/payment/vnpay-return',json=failed)
    with Session(pair.pay) as db:
        assert db.scalar(select(Payment)).status=='PAID'
        assert db.scalar(select(Case).where(Case.reason=='AMOUNT_MISMATCH')).status=='OPEN'
    with Session(pair.book) as db: assert db.get(Booking,bid).payment_status=='PAID' and not list(db.scalars(select(Ticket)))
    data=pair.pc.get(f'/payment/status/{bid}',headers=AUTH).json()
    assert data['fulfillment_status']=='REQUIRES_REVIEW' and data['requires_review']


def test_auth_private_checkout_and_single_owner_fence(pair):
    bid=new_order(pair)
    assert pair.pc.post('/payment/vnpay-url',json={'bookingId':bid}).status_code==401
    assert pair.bc.get(f'/internal/v1/checkouts/{bid}').status_code==401
    pair.state['user_id']=2
    assert pair.pc.post('/payment/vnpay-url',headers=AUTH,json={'bookingId':bid}).status_code==403
    assert pair.pc.get(f'/payment/status/{bid}',headers=AUTH).status_code==403
    pair.state['user_id']=1; start(pair,bid)
    pair.state['user_id']=2
    assert pair.pc.get(f'/payment/status/{bid}',headers=AUTH).status_code==403
    assert pair.pc.get('/admin/payment-reconciliation',headers=AUTH).status_code==403
    assert pair.bc.post('/payment/vnpay-url',headers=AUTH,json={'bookingId':bid}).status_code==410
    with pytest.raises(DBAPIError):
        with pair.book.begin() as conn: conn.execute(text("INSERT INTO payments(booking_id,provider,payment_method,merchant_ref,amount,currency,status,created_at,updated_at,checkout_version) VALUES (:id,'VNPAY','VNPAY','forbidden',150000,'VND','PENDING',now(),now(),1)"),{'id':bid})


def test_two_paid_attempts_never_duplicate_tickets_and_failure_is_not_booking_failure(pair):
    bid=new_order(pair); first=start(pair,bid)
    failure=signed(pair,first,vnp_ResponseCode='24',vnp_TransactionStatus='02')
    assert pair.pc.post('/payment/vnpay-return',json=failure).json()['provider_status']=='FAILED'
    with Session(pair.book) as db: assert db.get(Booking,bid).booking_status=='PENDING'
    second=start(pair,bid); assert first['vnp_TxnRef']!=second['vnp_TxnRef']
    pair.pc.post('/payment/vnpay-return',json=signed(pair,second)); deliver(pair)
    pair.pc.post('/payment/vnpay-return',json=signed(pair,first)); result=deliver(pair)
    assert result.data['reason']=='DUPLICATE_PAYMENT'
    with Session(pair.pay) as db:
        assert len(list(db.scalars(select(Payment).where(Payment.status=='PAID'))))==2
        assert db.scalar(select(Case).where(Case.reason=='DUPLICATE_PAYMENT'))
    with Session(pair.book) as db:
        assert len(list(db.scalars(select(Ticket))))==2 and db.get(Booking,bid).booking_status=='CONFIRMED'
        assert len(list(db.scalars(select(PaymentReceipt))))==2


def test_late_paid_cannot_take_seats_from_new_reservation(pair,monkeypatch):
    monkeypatch.setattr(booking_settings,'hold_seconds',1)
    bid=new_order(pair); url=start(pair,bid); time.sleep(1.1)
    from booking_service.worker import tick
    tick(pair.book)
    with Session(pair.book) as db: rid=reservations.hold(db,1,[1,2],2)[0]['reservation_id']
    pair.pc.post('/payment/vnpay-return',json=signed(pair,url)); result=deliver(pair)
    assert result.data['reason']=='RESERVATION_EXPIRED'
    with Session(pair.book) as db:
        assert db.get(Booking,bid).payment_status=='PAID' and db.get(Booking,bid).booking_status=='EXPIRED'
        assert not list(db.scalars(select(Ticket)))
        assert all(s.reservation_id==rid and s.hold_by_user_id==2 and s.status=='HOLD' for s in db.scalars(select(SeatStatus)))
    with Session(pair.pay) as db: assert db.scalar(select(Case).where(Case.reason=='BOOKING_REJECTED'))


def test_booking_transaction_rolls_back_tickets_inbox_and_outbox_then_recovers(pair,monkeypatch):
    bid=new_order(pair); capture(pair,bid); event=event_from(pair.pay,'PaymentCaptured.v1')
    original=payment_saga.booking_confirmed
    def crash(*args,**kwargs): raise RuntimeError('consumer crashed after ticket insert before commit')
    monkeypatch.setattr(payment_saga,'booking_confirmed',crash)
    with pytest.raises(RuntimeError):
        with Session(pair.book) as db,db.begin(): payment_saga.receive(db,event)
    with Session(pair.book) as db:
        assert not list(db.scalars(select(Ticket))) and not list(db.scalars(select(PaymentReceipt))) and not list(db.scalars(select(InboxRecord)))
        assert db.get(Booking,bid).booking_status=='PENDING'
    monkeypatch.setattr(payment_saga,'booking_confirmed',original); deliver(pair,event)


def test_parallel_callback_and_capture_consumers_are_idempotent(pair):
    bid=new_order(pair); body=signed(pair,start(pair,bid))
    def callback(_): return pair.pc.post('/payment/vnpay-ipn',json=body).json()['RspCode']
    with ThreadPoolExecutor(4) as pool: assert sorted(pool.map(callback,range(4)))==['00','02','02','02']
    event=event_from(pair.pay,'PaymentCaptured.v1')
    def consume(_):
        with Session(pair.book) as db,db.begin(): return payment_saga.receive(db,event)
    with ThreadPoolExecutor(4) as pool: assert list(pool.map(consume,range(4))).count(True)==1
    with Session(pair.book) as db: assert len(list(db.scalars(select(Ticket))))==2


def test_reconciliation_repairs_missing_result_and_audits_retry(pair,monkeypatch):
    bid=new_order(pair); capture(pair,bid)
    event=event_from(pair.pay,'PaymentCaptured.v1')
    with Session(pair.book) as db,db.begin(): payment_saga.receive(db,event)
    assert reconcile.tick(pair.pay)==0
    assert pair.pc.get(f'/payment/status/{bid}',headers=AUTH).json()['fulfillment_status']=='ISSUED'
    # Poll again is stable and the later real broker ACK is harmless.
    reconcile.tick(pair.pay)
    with Session(pair.pay) as db,db.begin(): service.receive_result(db,event_from(pair.book,'PaymentBookingResult.v1'))
    with Session(pair.pay) as db,db.begin(): service.open_case(db,1,'EVENT_BLOCKED')
    pair.state['permissions']=['reports.view']
    res=pair.pc.get('/admin/payment-reconciliation',headers=AUTH); case=res.json()['items'][0]
    assert case['booking_id']==bid and case['expected_amount']=='150000.00' and case['provider_status']=='PAID'
    assert pair.pc.post('/admin/payment-reconciliation/'+case['id']+'/retry',headers=AUTH,json={'reason':'   '}).status_code==422
    res=pair.pc.post('/admin/payment-reconciliation/'+case['id']+'/retry',headers=AUTH,json={'reason':'Verify delivery after broker recovery'})
    assert res.status_code==200 and res.json()['queued']
    with Session(pair.pay) as db: assert db.scalar(select(ReplayAudit)).reason=='Verify delivery after broker recovery'


def test_provider_evidence_and_ledger_are_immutable(pair):
    bid=new_order(pair); capture(pair,bid)
    for sql in ["UPDATE provider_results SET amount=1","DELETE FROM provider_results","UPDATE payment_checkouts SET amount=1","UPDATE payments SET status='FAILED'","UPDATE payments SET merchant_ref='rewrite'"]:
        with pytest.raises(DBAPIError):
            with pair.pay.begin() as conn: conn.execute(text(sql))


def test_real_broker_commit_before_ack_and_transport_outage(pair):
    bid=new_order(pair); capture(pair,bid)
    def unavailable(destination,event): raise ConnectionError('isolated broker unavailable')
    assert relay_one(pair.pay,unavailable,max_attempts=1)
    with Session(pair.pay) as db,db.begin():
        row=db.scalar(select(OutboxRecord)); assert row.status=='BLOCKED'
        assert db.scalar(select(Payment)).status=='PAID'
        reconcile.retry_capture(db,1)
    operator=connect(os.environ['TEST_AMQP_OPERATOR_PUBLIC']); channel=operator.channel()
    channel.queue_purge('booking.payment.v1')
    publisher=Publisher(os.environ['PAYMENT_AMQP_PUBLIC_URL'],os.environ['PAYMENT_AMQP_PUBLIC_URL'])
    try:
        assert relay_one(pair.pay,publisher)
        method,props,body=channel.basic_get('booking.payment.v1',auto_ack=False); assert method
        event=EventEnvelope.model_validate_json(body)
        with Session(pair.book) as db,db.begin(): assert payment_saga.receive(db,event)
        # Close with no ACK: a crashed consumer must redeliver committed work.
        channel.close(); channel=operator.channel()
        method,props,body=channel.basic_get('booking.payment.v1',auto_ack=False)
        assert method.redelivered
        with Session(pair.book) as db,db.begin(): assert payment_saga.receive(db,EventEnvelope.model_validate_json(body)) is False
        channel.basic_ack(method.delivery_tag)
        with Session(pair.book) as db: assert len(list(db.scalars(select(Ticket))))==2
    finally: publisher.close(); operator.close()


def test_checkout_events_delivered_out_of_order_do_not_reopen_expired_attempt(pair,monkeypatch):
    from payment_service.worker import receive
    monkeypatch.setattr(booking_settings,'hold_seconds',1)
    bid=new_order(pair); created=event_from(pair.book,'CheckoutCreated.v1'); start(pair,bid)
    time.sleep(1.1)
    from booking_service.worker import tick
    tick(pair.book); expired=event_from(pair.book,'BookingExpired.v1')
    with Session(pair.pay) as db,db.begin(): assert receive(db,expired)
    with Session(pair.pay) as db,db.begin(): assert receive(db,created)
    with Session(pair.pay) as db: assert db.scalar(select(Payment)).status=='CANCELLED'
    with Session(pair.pay) as db,db.begin(): assert receive(db,expired) is False


def test_reconciliation_detects_blocked_capture_without_downgrading_paid(pair,monkeypatch):
    bid=new_order(pair); capture(pair,bid)
    def unavailable(*args): raise ConnectionError()
    relay_one(pair.pay,unavailable,max_attempts=1)
    clock=now()+timedelta(seconds=31); monkeypatch.setattr(reconcile,'now',lambda:clock)
    assert reconcile.tick(pair.pay)==2
    with Session(pair.pay) as db:
        assert set(db.scalars(select(Case.reason)))=={'EVENT_BLOCKED','PAID_UNCONFIRMED'}
        assert db.scalar(select(OutboxRecord)).status=='BLOCKED' and db.scalar(select(Payment)).status=='PAID'
    deliver(pair)
    with Session(pair.pay) as db: assert set(db.scalars(select(Case.status)))=={'RESOLVED'}


def test_real_worker_processes_consume_only_owned_queues_and_dead_letter_poison(pair):
    import subprocess,sys
    bid=new_order(pair); capture(pair,bid)
    operator=connect(os.environ['TEST_AMQP_OPERATOR_PUBLIC']); channel=operator.channel()
    for queue in ['booking.payment.v1','booking.payment.v1.dead','payment.booking.v1','payment.booking.v1.dead']: channel.queue_purge(queue)
    env={**os.environ,'BOOKING_WRITES_ENABLED':'true','PAYMENT_WRITES_ENABLED':'true'}
    process=subprocess.Popen([sys.executable,'-m','booking_service.payment_consumer'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    payment_process=None
    pp=Publisher(os.environ['PAYMENT_AMQP_PUBLIC_URL'],os.environ['PAYMENT_AMQP_PUBLIC_URL'])
    bp=Publisher(os.environ['AMQP_PUBLIC_URL'],os.environ['AMQP_NOTIFICATION_URL'])
    try:
        relay_one(pair.pay,pp)
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            with Session(pair.book) as db:
                if db.scalar(select(func.count()).select_from(Ticket))==2: break
            time.sleep(.1)
        else: pytest.fail('Booking consumer did not issue tickets')
        channel.basic_publish('cinema.events.v1','PaymentCaptured.v1',b'bad-json')
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            method,_,body=channel.basic_get('booking.payment.v1.dead',auto_ack=True)
            if method: assert body==b'bad-json'; break
            time.sleep(.1)
        else: pytest.fail('Poison capture did not reach DLQ')
        payment_process=subprocess.Popen([sys.executable,'-m','payment_service.worker'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        # Publish only the Booking result. Checkout events are verified through HTTP
        # in a separate test, while this process has no network Booking fixture.
        result=event_from(pair.book,'PaymentBookingResult.v1'); bp('public',result)
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            with Session(pair.pay) as db:
                if db.get(Fulfillment,1).outcome=='CONFIRMED': break
            time.sleep(.1)
        else: pytest.fail('Payment consumer did not record Booking acknowledgement')
    finally:
        process.terminate(); process.wait(timeout=10)
        if payment_process: payment_process.terminate(); payment_process.wait(timeout=10)
        pp.close(); bp.close(); operator.close()


def test_payment_runtime_has_no_booking_orm_or_foreign_db_credential():
    import ast
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]/'src/payment_service'
    for path in root.glob('*.py'):
        if path.name=='migrate.py': continue
        code=path.read_text(); tree=ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom): assert not (node.module or '').startswith(('booking_service','app.'))
        assert 'SOURCE_DATABASE_URL' not in code and 'BOOKING_DATABASE_URL' not in code
    from payment_service.models import Base
    assert all(fk.column.table.name in Base.metadata.tables for table in Base.metadata.tables.values() for fk in table.foreign_keys)
