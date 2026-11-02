import os
from datetime import datetime,timezone,date,time,timedelta
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import create_engine,MetaData,Table,text,select
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session
import pytest
from booking_service.migrate import TABLES,transfer
from booking_service.models import Booking,Checkout,Reservation,Payment,Ticket
from booking_service.schemas.sales import SalesSnapshot
from cinema_platform.events import OutboxRecord,EventEnvelope


@pytest.mark.parametrize('corrupt',[False,True])
def test_actual_source_copy_preserves_history_checkout_deadline_and_message_identity(booking_store,corrupt):
    root=create_engine(os.environ['TEST_POSTGRES_URL']); schema='booking_copy_'+uuid4().hex
    with root.begin() as conn: conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    source=create_engine(os.environ['TEST_POSTGRES_URL'],connect_args={'options':f'-csearch_path={schema}'})
    try:
        metadata=MetaData()
        for name in TABLES: Table(name,metadata,autoload_with=root,resolve_fks=False)
        metadata.create_all(source)
        stamp=datetime.now(timezone.utc)-timedelta(days=1)
        pub=SalesSnapshot(showtime_id=1,sales_version=1,catalog_binding_id=uuid4(),film_id=101,format_id=201,
            film=dict(id=101,title='Historical title',catalog_version=1,format_ids=[201],format_name='2D'),room=dict(id=301,theater_id=401,name='Room',capacity=10,status='ACTIVE'),
            theater=dict(id=401,name='Theater',address='Test',city='Test'),show_date=date.today()+timedelta(days=5),start_time=time(18),end_time=time(20),status='ACTIVE',seat_count=2,
            seats=[dict(id=i,seat_name=f'A{i}',seat_type_id=501,seat_type='Standard',price='75000.00',status='ACTIVE') for i in [1,2]])
        envelope=EventEnvelope(event_type='BookingConfirmed.v1',producer='booking-monolith',aggregate_id='booking:41',aggregate_version=1,correlation_id='booking:41',data={'booking_id':41})
        with source.begin() as conn:
            conn.execute(text("CREATE TABLE domain_ownership(domain text PRIMARY KEY,owner text); INSERT INTO domain_ownership VALUES ('booking','maintenance')"))
            conn.execute(metadata.tables['booking_sales_configurations'].insert().values(showtime_id=1,sales_version=1,digest=pub.digest(),film_id=101,room_id=301,theater_id=401,show_date=pub.show_date,start_time=pub.start_time,end_time=pub.end_time,status='ACTIVE',snapshot=pub.model_dump(mode='json'),imported_at=stamp))
            conn.execute(metadata.tables['booking_sales_gates'].insert().values(showtime_id=1,sales_version=1,epoch=3,action='OPEN',is_open=True))
            for i,status,payment in [(41,'CONFIRMED','PAID'),(42,'EXPIRED','FAILED')]:
                conn.execute(metadata.tables['bookings'].insert().values(id=i,user_id=99,showtime_id=1,booking_date=stamp,total_amount='75000.00',payment_method='VNPAY',booking_status=status,payment_status=payment,created_at=stamp,expires_at=None,sales_version=1,catalog_film_snapshot=pub.film,customer_full_name='Historical customer',customer_email='copy@example.test'))
                conn.execute(metadata.tables['booking_details'].insert().values(id=i+10,booking_id=i,seat_id=i-40,price='75000.00'))
                conn.execute(metadata.tables['seat_status'].insert().values(id=i,showtime_id=1,seat_id=i-40,status='BOOKED' if i==41 and not corrupt else 'AVAILABLE',version=2,sales_version=1,created_at=stamp,updated_at=stamp))
            conn.execute(metadata.tables['payments'].insert().values(id=61,booking_id=41,provider='VNPAY',payment_method='VNPAY',merchant_ref='copy-reference',amount='75000.00',currency='VND',status='PAID',paid_at=stamp,created_at=stamp,updated_at=stamp))
            conn.execute(metadata.tables['tickets'].insert().values(id=71,booking_detail_id=51,ticket_code='copy-ticket',status='ISSUED',issued_at=stamp))
            conn.execute(metadata.tables['outbox_events'].insert().values(event_id=str(envelope.event_id),event_type=envelope.event_type,aggregate_id=envelope.aggregate_id,aggregate_version=1,payload=envelope.model_dump(mode='json'),destination='public',status='PUBLISHED',attempts=1,available_at=stamp,published_at=stamp,created_at=stamp))
            for name in ('bookings','booking_details','booking_food_items','payments','tickets','seat_status'):
                conn.execute(text("SELECT setval(pg_get_serial_sequence(:name,'id'),3000000,true)"),{'name':name})
        with pytest.raises(ValueError): transfer(source,booking_store,apply=True)
        if corrupt:
            with pytest.raises(ValueError): transfer(source,booking_store,apply=True,frozen=True)
            with Session(booking_store) as db: assert not list(db.scalars(select(Booking)))
            with source.begin() as conn: conn.execute(text("UPDATE seat_status SET status='BOOKED' WHERE seat_id=1"))
        result=transfer(source,booking_store,apply=True,frozen=True)
        assert result['verified'] and result['copied'] and len(result['tables'])==11
        assert transfer(source,booking_store)['verified']
        assert not transfer(source,booking_store,apply=True,frozen=True)['copied']
        with Session(booking_store) as db:
            booking=db.get(Booking,41); checkout=db.get(Checkout,41)
            assert booking.expires_at is None and checkout.deadline==stamp+timedelta(minutes=10)
            assert booking.reservation_id and checkout.reservation_id==booking.reservation_id
            assert db.get(Reservation,booking.reservation_id).status=='CONFIRMED'
            assert checkout.amount==Decimal('75000.00') and db.get(Payment,61).checkout_version==1
            assert db.get(Ticket,71).ticket_code=='copy-ticket'
            assert db.get(OutboxRecord,str(envelope.event_id)).payload==envelope.model_dump(mode='json')
        with pytest.raises(DBAPIError):
            with booking_store.begin() as conn: conn.execute(text('UPDATE checkout_snapshots SET amount=1'))
        with booking_store.begin() as conn:
            assert conn.execute(text("SELECT nextval(pg_get_serial_sequence('bookings','id'))")).scalar_one()>3000000
            conn.execute(text("UPDATE payments SET updated_at=updated_at+interval '1 second' WHERE id=61"))
        with pytest.raises(ValueError): transfer(source,booking_store,apply=True,frozen=True)
    finally:
        source.dispose()
        with root.begin() as conn: conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()
