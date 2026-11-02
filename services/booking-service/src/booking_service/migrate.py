"""Privileged one-shot copy/verify, never used by the runtime API.

Copies eleven allowlisted transaction/projection/messaging tables. Refuses to overwrite divergent data.
"""

import argparse
from datetime import date, datetime, time, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import MetaData, Table, Integer, cast, create_engine, func, select, text
from sqlalchemy.engine import make_url

from .config import Settings
from .models import Model,SalesBase
from cinema_platform.events import MessagingBase
TABLE_MAP={**Model.metadata.tables,**SalesBase.metadata.tables,**MessagingBase.metadata.tables}

TABLES = ("booking_sales_configurations","booking_sales_gates","bookings","booking_details","booking_food_items","payments","tickets","seat_status","outbox_events","inbox_events","message_replay_audits")


def canonical(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, (UUID, date, time, Decimal)):
        return str(value)
    raise TypeError(type(value).__name__)


def snapshot(connection, tables, columns):
    summary = {}
    for name in TABLES:
        table = tables[name]
        digest, count = hashlib.sha256(), 0
        rows = connection.execution_options(stream_results=True).execute(select(*(table.c[c] for c in columns[name])).order_by(*table.primary_key.columns)).mappings()
        for row in rows:
            digest.update(json.dumps(dict(row), sort_keys=True, ensure_ascii=False, default=canonical, separators=(",", ":")).encode() + b"\n")
            count += 1
        rows.close()
        connection.execution_options(stream_results=False)
        summary[name] = {"rows": count, "sha256": digest.hexdigest()}
    return summary


def sequence_value(connection, name):
    return connection.execute(text("""SELECT last_value FROM pg_sequences
        WHERE schemaname=current_schema()
        AND sequencename=split_part(pg_get_serial_sequence(:name, 'id'), '.', 2)"""), {"name": name}).scalar_one_or_none() or 0


def reseed(source, destination):
    for name in ("bookings","booking_details","booking_food_items","payments","tickets","seat_status"):
        max_id = source.execute(select(func.max(TABLE_MAP[name].c.id))).scalar_one() or 0
        maximum = max(max_id, sequence_value(source, name), sequence_value(destination, name))
        destination.execute(text("SELECT setval(pg_get_serial_sequence(:name, 'id'), :value, :called)"), {"name": name, "value": max(maximum, 1), "called": maximum > 0})


def bootstrap(db):
    from uuid import NAMESPACE_URL,uuid5
    from datetime import timedelta
    from .models import Booking,BookingDetail,SeatStatus,Reservation,Checkout,SalesConfiguration
    from .checkout import create_checkout,deadline
    from sqlmodel import select
    for booking in db.exec(select(Booking).order_by(Booking.id)):
        if not db.get(SalesConfiguration,(booking.showtime_id,booking.sales_version)): raise ValueError("Missing sales history")
        details=list(db.exec(select(BookingDetail).where(BookingDetail.booking_id==booking.id).order_by(BookingDetail.seat_id)))
        rid=str(uuid5(NAMESPACE_URL,"cinema:legacy-booking:"+str(booking.id)))
        status="CONFIRMED" if booking.booking_status=="CONFIRMED" else "EXPIRED" if booking.booking_status=="EXPIRED" else "RELEASED" if booking.booking_status=="CANCELLED" else "CHECKOUT"
        db.add(Reservation(id=rid,user_id=booking.user_id,showtime_id=booking.showtime_id,sales_version=booking.sales_version,seat_ids=[d.seat_id for d in details],status=status,expires_at=deadline(booking),created_at=booking.booking_date))
        db.flush(); booking.reservation_id=rid; db.add(booking); db.flush()
        create_checkout(db,booking)
        if status=="CONFIRMED":
            for detail in details:
                seat=db.exec(select(SeatStatus).where(SeatStatus.showtime_id==booking.showtime_id,SeatStatus.seat_id==detail.seat_id,SeatStatus.status=="BOOKED")).first()
                if seat is None or seat.reservation_id: raise ValueError("Ambiguous booked-seat ownership")
                seat.reservation_id=rid; db.add(seat)
    db.flush()
    if db.exec(select(SeatStatus).where(SeatStatus.status=="BOOKED",SeatStatus.reservation_id.is_(None))).first(): raise ValueError("Booked seat has no confirmed order")


def transfer(source,target,*,apply=False,frozen=False):
    if apply and not frozen: raise ValueError("Freeze Booking source and target writers before copy")
    if source.url==target.url: raise ValueError("Separate databases required")
    reflected={name:Table(name,MetaData(),autoload_with=source) for name in TABLES}
    columns={name:list(table.c.keys()) for name,table in reflected.items()}
    with source.connect().execution_options(isolation_level="REPEATABLE READ") as src,src.begin():
        src.execute(text("SET TRANSACTION READ ONLY"))
        if apply:
            if src.execute(text("SELECT owner FROM domain_ownership WHERE domain='booking'")).scalar_one()!="maintenance": raise ValueError("Source is not fenced")
            if src.execute(text("SELECT count(*) FROM seat_status WHERE status='HOLD' AND hold_expired_at>CURRENT_TIMESTAMP")).scalar_one(): raise ValueError("Wait for live holds")
            if src.execute(text("SELECT count(*) FROM bookings WHERE booking_status='PENDING' AND COALESCE(expires_at,booking_date+interval '10 minutes')>CURRENT_TIMESTAMP")).scalar_one(): raise ValueError("Wait for pending checkout")
        if apply and src.execute(text("SELECT count(*) FROM bookings WHERE booking_status='PENDING'")).scalar_one(): raise ValueError("Run legacy expiry cleanup and drain all pending orders before freeze")
        before=snapshot(src,reflected,columns)
        with target.begin() as dst:
            dst.execute(text("SELECT pg_advisory_xact_lock(78433268)"))
            current=snapshot(dst,TABLE_MAP,columns)
            if current==before:
                # Initial copy with zero orders is also safe to repeat; never rewrite
                # technical checkout/reservation fields on a verified destination.
                if apply: reseed(src,dst)
                return dict(verified=True,copied=False,tables=before)
            if not apply: raise ValueError("Booking source/target checksums differ")
            if any(item['rows'] for item in current.values()) or dst.execute(text('SELECT count(*) FROM reservations')).scalar_one(): raise ValueError("Nonempty destination differs; refusing overwrite")
            # Dedicated frozen migration profile only. Disable user triggers inside
            # this single locked transaction for historical BOOKED rows; re-enable
            # before commit after all old columns, ownership and snapshots verify.
            for name in TABLES: dst.execute(text(f'ALTER TABLE {name} DISABLE TRIGGER USER'))
            for name in TABLES:
                rows=src.execution_options(stream_results=True).execute(select(reflected[name]).order_by(*reflected[name].primary_key.columns)).mappings()
                while batch:=rows.fetchmany(500): dst.execute(TABLE_MAP[name].insert(),[dict(r) for r in batch])
                rows.close(); src.execution_options(stream_results=False)
            if snapshot(dst,TABLE_MAP,columns)!=before: raise ValueError("Post-copy original-column checksum mismatch")
            from sqlmodel import Session
            with Session(bind=dst,join_transaction_mode="create_savepoint") as db:
                bootstrap(db); db.commit()
            if snapshot(dst,TABLE_MAP,columns)!=before: raise ValueError("Bootstrap changed original financial/history facts")
            for name in TABLES: dst.execute(text(f'ALTER TABLE {name} ENABLE TRIGGER USER'))
            reseed(src,dst)
    return dict(verified=True,copied=True,tables=before)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--source-host',default='postgres')
    parser.add_argument('--source-port',type=int,default=5432)
    parser.add_argument('--source-origin',default='http://fastapi:8000')
    parser.add_argument('--destination-origin',default='http://booking-service:8087')
    parser.add_argument('--manifest',default='/tmp/booking-copy-manifest.json')
    args=parser.parse_args(); settings=Settings()
    with httpx.Client(timeout=5,trust_env=False) as http:
        headers={'X-Service-Key':settings.service_key}
        src_state=http.get(args.source_origin+'/internal/v1/booking-read/ownership',headers=headers)
        dst_state=http.get(args.destination_origin+'/internal/v1/migration/state',headers=headers)
        src_state.raise_for_status(); dst_state.raise_for_status()
        frozen=src_state.json()['owner']=='maintenance' and not dst_state.json()['writes_enabled']
    source=create_engine(make_url(os.environ['DATABASE_URL']).set(host=args.source_host,port=args.source_port))
    result=transfer(source,create_engine(settings.database_url),apply=args.apply,frozen=frozen)
    Path(args.manifest).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(verified=result['verified'],copied=result['copied'],rows={name:row['rows'] for name,row in result['tables'].items()})))

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('Booking migration failed; type='+type(exc).__name__+('; '+str(exc)[:200] if isinstance(exc,ValueError) else ''))
        raise SystemExit(1)
