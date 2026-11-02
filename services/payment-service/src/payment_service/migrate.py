"""Offline privileged copy; runtime Payment never receives a Booking DB credential."""
import argparse,hashlib,json,os
from datetime import datetime,timezone,date
from decimal import Decimal
from pathlib import Path
import httpx
from sqlalchemy import MetaData,Table,create_engine,select,text,func
from .config import Settings
from .models import Base,Checkout,Payment,ProviderResult,Fulfillment,Case


def canonical(value):
    if isinstance(value,datetime): return value.astimezone(timezone.utc).isoformat()
    if isinstance(value,(Decimal,date)): return str(value)
    raise TypeError(type(value).__name__)


def checksum(rows):
    return hashlib.sha256(b''.join(json.dumps(dict(row),sort_keys=True,default=canonical,separators=(',',':')).encode()+b'\n' for row in rows)).hexdigest()


def transfer(source,target,*,apply=False,frozen=False):
    if source.url==target.url: raise ValueError('Separate databases required')
    if apply and not frozen: raise ValueError('Freeze source callback owner and destination writes')
    with source.connect().execution_options(isolation_level='REPEATABLE READ') as src,src.begin():
        src.execute(text('SET TRANSACTION READ ONLY'))
        if apply:
            if src.execute(text('SELECT owner FROM payment_ownership WHERE id=1')).scalar_one()!='maintenance': raise ValueError('Source Payment owner must be fenced')
            if src.execute(text("SELECT count(*) FROM bookings WHERE booking_status='PENDING'")).scalar_one(): raise ValueError('Drain pending checkouts before copy')
            if src.execute(text("SELECT count(*) FROM seat_status WHERE status='HOLD' AND hold_expired_at>CURRENT_TIMESTAMP")).scalar_one(): raise ValueError('Wait for active holds')
        table=Table('payments',MetaData(),autoload_with=src,resolve_fks=False)
        columns=list(table.c.keys())
        rows=[dict(r) for r in src.execute(select(table).order_by(table.c.id)).mappings()]
        facts=[dict(r) for r in src.execute(text('''SELECT c.booking_id,c.booking_version,c.reservation_id,b.user_id,c.amount,c.currency,c.deadline,c.digest,
            b.payment_method,b.booking_date FROM checkout_snapshots c JOIN bookings b ON b.id=c.booking_id
            WHERE EXISTS (SELECT 1 FROM payments p WHERE p.booking_id=c.booking_id) ORDER BY c.booking_id,c.booking_version''')).mappings()]
        receipts={r['payment_id']:dict(r) for r in src.execute(text('SELECT * FROM booking_payment_receipts')).mappings()}
        highwater=max(src.execute(text("SELECT last_value FROM pg_sequences WHERE schemaname=current_schema() AND sequencename=split_part(pg_get_serial_sequence('payments','id'),'.',2)")).scalar_one_or_none() or 0,max([r['id'] for r in rows],default=0))
        for row in rows:
            if row['status']=='PAID' and row['id'] not in receipts: raise ValueError('Historical PAID has no Booking confirmation evidence')
        with target.begin() as dst:
            dst.execute(text('SELECT pg_advisory_xact_lock(78433269)'))
            actual=[dict(r) for r in dst.execute(select(*(Payment.__table__.c[c] for c in columns)).order_by(Payment.id)).mappings()]
            targetfacts=[dict(r) for r in dst.execute(select(*(Checkout.__table__.c[c] for c in facts[0] if c!='primary_payment_id')).order_by(Checkout.booking_id,Checkout.booking_version)).mappings()] if facts else []
            same=checksum(actual)==checksum(rows) and checksum(targetfacts)==checksum(facts)
            if not same:
                if not apply: raise ValueError('Payment source/destination checksums differ')
                if any(dst.scalar(select(func.count()).select_from(model)) for model in (Payment,Checkout,ProviderResult,Fulfillment,Case)): raise ValueError('Nonempty divergent destination; refusing overwrite')
                if facts: dst.execute(Checkout.__table__.insert(),facts)
                if rows: dst.execute(Payment.__table__.insert(),rows)
                for row in rows:
                    # Transfer evidence is explicitly distinguished from a signed callback.
                    dst.execute(ProviderResult.__table__.insert().values(id=hashlib.sha256(f"legacy:{row['id']}".encode()).hexdigest(),payment_id=row['id'],amount=row['amount'],transaction_ref=row['transaction_ref'] or '0',response_code='LEGACY',transaction_status=row['status'],success=row['status']=='PAID',origin='LEGACY_TRANSFER',received_at=row['updated_at']))
                    if row['status']=='PAID':
                        receipt=receipts[row['id']]
                        dst.execute(Fulfillment.__table__.insert().values(payment_id=row['id'],outcome=receipt['outcome'],reason=receipt['reason'],updated_at=receipt['created_at']))
                        if receipt['outcome']=='CONFIRMED': dst.execute(Checkout.__table__.update().where(Checkout.booking_id==row['booking_id'],Checkout.booking_version==row['checkout_version']).values(primary_payment_id=row['id']))
                        else:
                            from uuid import uuid5,NAMESPACE_URL
                            dst.execute(Case.__table__.insert().values(id=str(uuid5(NAMESPACE_URL,f"legacy-payment:{row['id']}")),payment_id=row['id'],reason='LEGACY_RECONCILIATION_REQUIRED',reference='',detail={},status='OPEN',created_at=row['updated_at'],updated_at=row['updated_at']))
                copied=True
            else: copied=False
            actual=list(dst.execute(select(*(Payment.__table__.c[c] for c in columns)).order_by(Payment.id)).mappings())
            if checksum(actual)!=checksum(rows): raise ValueError('Original financial-column checksum mismatch')
            if apply: dst.execute(text("SELECT setval(pg_get_serial_sequence('payments','id'),:value,:called)"),{'value':max(1,highwater),'called':highwater>0})
    return dict(verified=True,copied=copied,payments=len(rows),payment_sha256=checksum(rows),checkouts=len(facts),checkout_sha256=checksum(facts),payment_sequence_highwater=highwater)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--apply',action='store_true'); parser.add_argument('--manifest',default='/tmp/payment-copy.json'); args=parser.parse_args()
    cfg=Settings()
    with httpx.Client(timeout=5,trust_env=False,headers={'X-Service-Key':cfg.service_key}) as http:
        src=http.get(cfg.booking_origin+'/internal/v1/payment-ownership'); src.raise_for_status()
        dst=http.get('http://payment-service:8088/internal/v1/migration/state'); dst.raise_for_status()
        frozen=src.json()['owner']=='maintenance' and not dst.json()['writes_enabled']
    result=transfer(create_engine(os.environ['PAYMENT_SOURCE_DATABASE_URL']),create_engine(cfg.database_url),apply=args.apply,frozen=frozen)
    Path(args.manifest).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('Payment migration failed; type='+type(exc).__name__+('; '+str(exc)[:200] if isinstance(exc,ValueError) else ''))
        raise SystemExit(1)
