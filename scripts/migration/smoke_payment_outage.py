"""Two-phase real RabbitMQ-stop rehearsal, isolated Payment DB schema only.

Start in the migration-test container. The operator stops rabbitmq-test then
touches /tmp/broker-stopped; after /tmp/outage-verified, restart the broker and
touch /tmp/broker-restored. No production provider, Booking or SMTP is contacted.
"""
import hashlib,hmac,json,os,time,urllib.parse
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
import httpx
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.engine import make_url
from sqlmodel import Session
from fastapi.testclient import TestClient
from cinema_platform.broker import connect,Publisher
from cinema_platform.events import OutboxRecord,EventEnvelope
from cinema_platform.outbox import relay_one
from cinema_platform.payment_contracts import CheckoutFact
from payment_service.config import Settings
from payment_service.models import Payment,ProviderResult
from payment_service.main import create_app
from payment_service import clients,reconcile


def wait_marker(name):
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        if Path('/tmp/'+name).exists(): return
        time.sleep(.2)
    raise TimeoutError(name)


def main():
    cfg=Settings()
    assert 'payment-db-test' in cfg.database_url and 'rabbitmq-test' in cfg.amqp_public_url
    root=create_engine(cfg.database_url);schema='payment_outage_'+uuid4().hex
    with root.begin() as conn:conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    url=make_url(cfg.database_url).update_query_dict({'options':f'-csearch_path={schema},public'})
    os.environ['PAYMENT_DATABASE_URL']=url.render_as_string(hide_password=False)
    engine=create_engine(url);publisher=Publisher(cfg.amqp_public_url,cfg.amqp_public_url)
    try:
        command.upgrade(Config('/workspace/services/payment-service/alembic.ini'),'head')
        cfg=Settings(writes_enabled=True)
        fact=CheckoutFact(booking_id=900000001,booking_version=1,reservation_id=uuid4(),user_id=1,amount='75000.00',currency='VND',deadline=datetime.now(timezone.utc)+timedelta(minutes=10),digest='a'*64,payment_method='Online',booking_date=datetime.now(timezone.utc),booking_status='PENDING',payment_status='PENDING')
        clients.checkout=lambda bid:fact
        app=create_app(cfg,engine=engine,auth_transport=httpx.MockTransport(lambda req:httpx.Response(200,json=dict(user_id=1,role='USER',is_active=True,permissions=[]))))
        with TestClient(app) as api:
            res=api.post('/payment/vnpay-url',headers={'Authorization':'Bearer fixture-token'},json={'bookingId':fact.booking_id});assert res.status_code==200,res.text
            params=dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(res.json()['paymentUrl']).query))
            body={k:params[k] for k in ['vnp_TxnRef','vnp_TmnCode','vnp_Amount']}
            body.update(vnp_ResponseCode='00',vnp_TransactionStatus='00',vnp_TransactionNo='isolated-outage-'+uuid4().hex)
            encoded='&'.join(f'{k}={urllib.parse.quote_plus(v)}' for k,v in sorted(body.items()))
            body['vnp_SecureHash']=hmac.new(cfg.hash_secret.encode(),encoded.encode(),hashlib.sha512).hexdigest()
            Path('/tmp/ready').touch();wait_marker('broker-stopped')
            assert api.post('/payment/vnpay-return',json=body).json()['fulfillment_status']=='PROCESSING'
            assert api.post('/payment/vnpay-ipn',json=body).json()['RspCode']=='02'
            assert relay_one(engine,publisher,max_attempts=1)
            with Session(engine) as db:
                row=db.scalar(select(OutboxRecord));event_id=row.event_id
                assert row.status=='BLOCKED' and row.attempts==1
                assert db.scalar(select(Payment)).status=='PAID'
                assert db.scalar(select(func.count()).select_from(ProviderResult))==1
            print('Stopped broker: signed callbacks committed once; PAID and blocked outbox retained.',flush=True)
            Path('/tmp/outage-verified').touch();wait_marker('broker-restored')
            operator=connect(os.environ['TEST_AMQP_OPERATOR_PUBLIC']);channel=operator.channel()
            try:
                channel.queue_purge('booking.payment.v1')
                with Session(engine) as db,db.begin(): assert reconcile.retry_capture(db,1)
                assert relay_one(engine,publisher)
                method,props,raw=channel.basic_get('booking.payment.v1',auto_ack=False);assert method and props.message_id==event_id
                assert EventEnvelope.model_validate_json(raw).data['payment_id']==1
                channel.basic_ack(method.delivery_tag)
                with Session(engine) as db:
                    assert db.scalar(select(OutboxRecord)).status=='PUBLISHED'
                    assert db.scalar(select(Payment)).status=='PAID'
                result=dict(stopped_broker_callback_committed=True,paid_retained=True,one_provider_result=True,stable_capture_delivered_after_restart=True)
                Path('/workspace/tmp/m9-broker-outage-result.json').write_text(json.dumps(result,indent=2)+'\n')
                print(json.dumps(result),flush=True)
            finally:operator.close()
    finally:
        publisher.close();engine.dispose()
        with root.begin() as conn:conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()

if __name__=='__main__':main()
