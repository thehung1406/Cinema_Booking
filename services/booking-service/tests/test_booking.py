from datetime import date,time,timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
import time as wall
from uuid import uuid4
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select,text,event
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session
from booking_service.config import Settings,settings
from booking_service.models import Model,SalesBase,Booking,BookingDetail,Reservation,Checkout,Idempotency,SeatStatus,Payment,Ticket
from booking_service.schemas.sales import SalesSnapshot
from booking_service.schemas.booking import BookingCreateRequest
from booking_service import reservations,bookings,sales
from booking_service.main import create_app
from booking_service.payments import PaymentService
from booking_service.payment_repo import PaymentRepository
from booking_service.worker import tick
from cinema_platform.events import OutboxRecord


@pytest.fixture
def ready(booking_store,monkeypatch):
    item=SalesSnapshot(showtime_id=1,sales_version=1,catalog_binding_id=uuid4(),film_id=2000001,format_id=2000002,
        film=dict(id=2000001,title='Only in Catalog',catalog_version=1,format_ids=[2000002],format_name='2D'),
        room=dict(id=2000003,theater_id=2000004,name='Only in Cinema',capacity=10,status='ACTIVE'),
        theater=dict(id=2000004,name='Independent theater',address='Test',city='Test'),show_date=date.today()+timedelta(days=5),start_time=time(18),end_time=time(20),status='ACTIVE',seat_count=2,
        seats=[dict(id=i,seat_name=f'A{i}',seat_type_id=100,seat_type='Standard',price='75000.00',status='ACTIVE') for i in [1,2]])
    with Session(booking_store) as db:
        sales.close(db,1,1); sales.install(db,item,item.digest(),2); sales.open_sales(db,1,1,item.digest(),3)
    monkeypatch.setattr('booking_service.bookings.contact',lambda uid:SimpleNamespace(full_name='Test',email='test@example.test',phone=None))
    return booking_store


def request(user=1,ids=(1,2),reservation=None,total=150000):
    return BookingCreateRequest(userId=user,showtimeId=1,totalAmount=total,paymentMethod='Online',reservationId=reservation,seats=[dict(seat_id=i,price=.01) for i in ids])

def params(payment):
    return dict(vnp_TxnRef=payment.merchant_ref,vnp_TmnCode=settings.tmn_code,vnp_Amount=str(int(payment.amount*100)),vnp_ResponseCode='00',vnp_TransactionStatus='00',vnp_TransactionNo=uuid4().hex)


def test_api_auth_reservation_checkout_retry_and_signed_return_keep_contract(ready):
    state=dict(user_id=1,role='USER',is_active=True,permissions=[])
    cfg=Settings(writes_enabled=True,hash_secret='isolated-custom-merchant-key-32-characters')
    app=create_app(cfg,engine=ready,auth_transport=httpx.MockTransport(lambda r:httpx.Response(200,json=state)))
    headers={'Authorization':'Bearer isolated-token'}
    with TestClient(app) as client:
        assert client.post('/seats/hold',json=dict(showtime_id=1,seat_ids=[1])).status_code==401
        first=client.post('/seats/hold',headers=headers,json=dict(showtime_id=1,seat_ids=[1])); assert first.status_code==200,first.text
        rid=first.json()[0]['reservation_id']; deadline=first.json()[0]['hold_expired_at']
        second=client.post('/seats/hold',headers=headers,json=dict(showtime_id=1,seat_ids=[2],reservation_id=rid))
        assert second.json()[0]['reservation_id']==rid and second.json()[0]['hold_expired_at']==deadline
        assert all(s['reservation_id'] is None for s in client.get('/seats/showtime/1').json())
        body=request(reservation=rid).model_dump(mode='json')
        response=client.post('/bookings',headers={**headers,'Idempotency-Key':'checkout-1'},json=body)
        assert response.status_code==201,response.text
        bid=response.json()['bookingId']
        assert client.post('/bookings',headers={**headers,'Idempotency-Key':'checkout-1'},json=body).json()==response.json()
        assert client.post('/bookings',headers={**headers,'Idempotency-Key':'checkout-1'},json={**body,'totalAmount':'1.00'}).status_code==409
        assert client.post('/seats/release',headers=headers,json=dict(showtime_id=1,seat_ids=[1],reservation_id=rid)).status_code==409
        url=client.post('/payment/vnpay-url',headers=headers,json=dict(bookingId=bid)); assert url.status_code==200,url.text
        assert client.post('/payment/vnpay-url',headers=headers,json=dict(bookingId=bid)).json()==url.json()
        with Session(ready) as db: payment=db.scalar(select(Payment).where(Payment.booking_id==bid)); payload=params(payment)
        import hashlib,hmac,urllib.parse
        encoded='&'.join(f'{k}={urllib.parse.quote_plus(str(v))}' for k,v in sorted(payload.items()))
        payload['vnp_SecureHash']=hmac.new(cfg.hash_secret.encode(),encoded.encode(),hashlib.sha512).hexdigest()
        result=client.get('/payment/vnpay-ipn',params=payload)
        assert result.json()['RspCode']=='00',result.text
        assert client.get('/payment/vnpay-ipn',params=payload).json()['RspCode']=='02'
        tickets=client.get(f'/tickets/booking/{bid}',headers=headers).json(); assert len(tickets)==2
        assert client.post('/tickets/'+tickets[0]['ticket_code']+'/check-in',headers=headers).status_code==403
        state['permissions']=['tickets.check_in']
        assert client.post('/tickets/'+tickets[0]['ticket_code']+'/check-in',headers=headers).status_code==200
        assert client.post('/tickets/'+tickets[0]['ticket_code']+'/check-in',headers=headers).status_code==409
        state['user_id']=2
        assert client.get(f'/bookings/{bid}',headers=headers).status_code==403
    with Session(ready) as db:
        assert len(list(db.scalars(select(Booking))))==1
        assert len(list(db.scalars(select(OutboxRecord))))==3
        checkout=db.get(Checkout,bid)
        assert checkout.amount==150000 and checkout.currency=='VND' and checkout.snapshot['seats'][0]['price']=='75000.00'


def test_atomic_multi_seat_hold_with_reverse_order_has_one_winner(ready):
    barrier=Barrier(2)
    def writer(user):
        with Session(ready) as db:
            barrier.wait(timeout=10)
            try: reservations.hold(db,1,[2,1] if user==1 else [1,2],user); return 200
            except HTTPException as exc: db.rollback(); return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: assert sorted(pool.map(writer,[1,2]))==[200,409]
    with Session(ready) as db:
        held=list(db.scalars(select(SeatStatus)))
        assert len(held)==2 and len({s.reservation_id for s in held})==1 and len({s.hold_by_user_id for s in held})==1


@pytest.mark.parametrize('same_key',[True,False])
def test_checkout_race_never_creates_two_orders_for_one_reservation(ready,same_key):
    with Session(ready) as db: rid=reservations.hold(db,1,[1,2],1)[0]['reservation_id']
    barrier=Barrier(2)
    def writer(index):
        with Session(ready) as db:
            barrier.wait(timeout=10)
            try: return bookings.create(db,request(reservation=rid),1,'same' if same_key else f'key-{index}')['bookingId']
            except HTTPException as exc: db.rollback(); return 'rejected'
    with ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(writer,[1,2]))
    if same_key: assert result[0]==result[1]
    else: assert result.count('rejected')==1
    with Session(ready) as db:
        assert len(list(db.scalars(select(Booking))))==1 and len(list(db.scalars(select(Checkout))))==1


def test_checkout_and_deadline_are_immutable_and_failed_multi_seat_hold_rolls_back(ready):
    with Session(ready) as db:
        rid=reservations.hold(db,1,[1],2)[0]['reservation_id']
    with Session(ready) as db:
        with pytest.raises(HTTPException): reservations.hold(db,1,[2,1],1)
        db.rollback()
        assert db.scalar(select(SeatStatus).where(SeatStatus.seat_id==2)) is None
        reservations.release(db,1,[1],2,rid)
        new_id=reservations.hold(db,1,[1,2],1)[0]['reservation_id']
        created=bookings.create(db,request(reservation=new_id),1,'immutable')
    for query in ["UPDATE checkout_snapshots SET amount=1","DELETE FROM checkout_snapshots","UPDATE bookings SET total_amount=1","UPDATE reservations SET expires_at=expires_at+interval '1 minute'","UPDATE booking_details SET price=1"]:
        with pytest.raises(DBAPIError):
            with ready.begin() as conn: conn.execute(text(query))


def test_expiry_and_late_payment_are_serialized_and_cannot_consume_new_hold(ready,monkeypatch):
    monkeypatch.setattr(settings,'hold_seconds',2)
    with Session(ready) as db:
        rid=reservations.hold(db,1,[1,2],1)[0]['reservation_id']
        result=bookings.create(db,request(reservation=rid),1,'expires')
        booking=db.get(Booking,result['bookingId']); payment=PaymentRepository.create_attempt(db,booking); payload=params(payment); bid=booking.id; db.commit()
    wall.sleep(2.1)
    barrier=Barrier(2)
    def run(index):
        barrier.wait(timeout=10)
        if index==0: return tick(ready)
        with Session(ready) as db: return PaymentService.confirm_vnpay_payment(db,bid,'00',payload)
    with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(run,[0,1]))
    with Session(ready) as db:
        assert db.get(Booking,bid).booking_status=='EXPIRED'
        assert db.scalar(select(Payment)).status=='PAID'
        assert not list(db.scalars(select(Ticket)))
        new_id=reservations.hold(db,1,[1,2],1)[0]['reservation_id']; assert new_id!=rid
        PaymentService.confirm_vnpay_payment(db,bid,'00',payload)
        assert {s.reservation_id for s in db.scalars(select(SeatStatus))}=={new_id}
        assert {s.status for s in db.scalars(select(SeatStatus))}=={'HOLD'}


def test_store_has_no_external_domain_tables_or_imports(ready):
    from pathlib import Path
    for path in (Path(__file__).resolve().parents[1]/'src').rglob('*.py'):
        content=path.read_text()
        assert 'from app.' not in content and 'import app.' not in content
    from sqlalchemy import inspect
    with ready.connect() as conn: schema=conn.exec_driver_sql('select current_schema()').scalar_one()
    names=set(inspect(ready).get_table_names(schema=schema))
    assert not names & {'users','films','showtimes','seats','theaters','reviews','ai_conversations'}


def test_failure_after_provider_validation_preserves_paid_evidence_and_retries_once(ready,monkeypatch):
    with Session(ready) as db:
        rid=reservations.hold(db,1,[1,2],1)[0]['reservation_id']
        result=bookings.create(db,request(reservation=rid),1,'failure')
        booking=db.get(Booking,result['bookingId']); attempt=PaymentRepository.create_attempt(db,booking); payload=params(attempt); bid=booking.id; db.commit()
    from booking_service.tickets import TicketService
    original=TicketService.issue_for_booking
    def fail(*args): raise RuntimeError('Injected ticket failure')
    monkeypatch.setattr(TicketService,'issue_for_booking',fail)
    with Session(ready) as db:
        with pytest.raises(HTTPException): PaymentService.confirm_vnpay_payment(db,bid,'00',payload)
        assert db.get(Booking,bid).payment_status=='PENDING'
        assert db.scalar(select(Payment)).status=='PAID'
        assert not list(db.scalars(select(Ticket))) and len(list(db.scalars(select(OutboxRecord))))==1
    monkeypatch.setattr(TicketService,'issue_for_booking',original)
    with Session(ready) as db:
        assert PaymentService.confirm_vnpay_payment(db,bid,'00',payload)['status']=='success'
        assert PaymentService.confirm_vnpay_payment(db,bid,'00',payload)['status']=='success'
        assert len(list(db.scalars(select(Ticket))))==2 and len(list(db.scalars(select(OutboxRecord))))==3
