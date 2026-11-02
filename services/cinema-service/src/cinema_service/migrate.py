"""Privileged one-shot copy/verify, never used by the runtime API.

Copies seven allowlisted Cinema tables and frozen schedule-reference facts. Refuses to overwrite divergent data.
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
from .models import Base

TABLES = ("theaters", "cinema_rooms", "seat_types", "seats", "showtimes")


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
    for name in TABLES:
        max_id = source.execute(select(func.max(Base.metadata.tables[name].c.id))).scalar_one() or 0
        maximum = max(max_id, sequence_value(source, name), sequence_value(destination, name))
        destination.execute(text("SELECT setval(pg_get_serial_sequence(:name, 'id'), :value, :called)"), {"name": name, "value": max(maximum, 1), "called": maximum > 0})


def transfer(source,target,*,apply=False,frozen=False):
    if apply and not frozen: raise ValueError("Freeze source and target before copying")
    if source.url==target.url: raise ValueError("Separate stores are required")
    reflected={name:Table(name,MetaData(),autoload_with=source) for name in TABLES}
    columns={name:list(table.c.keys()) for name,table in reflected.items()}
    with source.connect().execution_options(isolation_level="REPEATABLE READ") as src, src.begin():
        src.execute(text("SET TRANSACTION READ ONLY"))
        before=snapshot(src,reflected,columns)
        with target.begin() as dst:
            dst.execute(text("SELECT pg_advisory_xact_lock(78433267)"))
            current=snapshot(dst,Base.metadata.tables,columns)
            if current==before:
                if apply: reseed(src,dst)
                return dict(verified=True,copied=False,tables=before)
            if not apply: raise ValueError("Cinema checksums differ")
            if any(item["rows"] for item in current.values()) or dst.execute(text("SELECT count(*) FROM cinema_operations")).scalar_one():
                raise ValueError("Destination is not empty; refusing overwrite")
            for name in TABLES:
                rows=src.execution_options(stream_results=True).execute(select(reflected[name]).order_by(*reflected[name].primary_key.columns)).mappings()
                while batch:=rows.fetchmany(500): dst.execute(Base.metadata.tables[name].insert(),[dict(row) for row in batch])
                rows.close(); src.execution_options(stream_results=False)
            reseed(src,dst)
            if snapshot(dst,Base.metadata.tables,columns)!=before: raise ValueError("Post-copy checksum mismatch")
    return dict(verified=True,copied=True,tables=before)


def bootstrap(source,target,clients):
    from sqlalchemy.orm import Session
    from uuid import uuid4
    from .models import Showtime,Publication,Operation,CinemaRoom
    from .service import snapshot as publication_snapshot, execute
    # No customer writes may be active; fill the migration reference for legacy rows
    # inserted between schema upgrade and freeze. Financial facts remain untouched.
    with source.begin() as conn:
        owner=conn.execute(text("SELECT owner FROM domain_ownership WHERE domain='cinema' FOR UPDATE")).scalar_one()
        if owner!="maintenance": raise ValueError("Bootstrap requires maintenance ownership")
        if conn.execute(text("SELECT count(*) FROM seat_status WHERE status='HOLD' AND hold_expired_at>CURRENT_TIMESTAMP")).scalar_one(): raise ValueError("Wait for holds to drain")
        if conn.execute(text("SELECT count(*) FROM bookings WHERE booking_status='PENDING' AND COALESCE(expires_at,booking_date+interval '10 minutes')>CURRENT_TIMESTAMP")).scalar_one(): raise ValueError("Wait for pending checkout")
        conn.execute(text("UPDATE bookings SET sales_version=1 WHERE sales_version IS NULL"))
        conn.execute(text("UPDATE seat_status SET sales_version=1,status=CASE WHEN status='HOLD' THEN 'AVAILABLE' ELSE status END,hold_by_user_id=NULL,hold_expired_at=NULL WHERE sales_version IS NULL"))
    with Session(target) as db:
        ids=list(db.scalars(select(Showtime.id).order_by(Showtime.id)))
    for show_id in ids:
        with Session(target) as db:
            show=db.get(Showtime,show_id)
            op_id="bootstrap-"+str(show_id)
            op=db.get(Operation,op_id)
            if op is None:
                if show.sales_version: raise ValueError("Unexpected existing publication")
                pub=publication_snapshot(db,show,1)
                show.control_epoch=1; show.sales_version=1; show.sales_state="CLOSED"
                db.add(Publication(showtime_id=show.id,sales_version=1,digest=pub.digest(),snapshot=pub.model_dump(mode="json")))
                op=Operation(id=op_id,room_id=show.room_id,kind="PUBLISH",target_id=show.id,payload={},
                    progress={"shows":[show.id],"rooms":[show.room_id]},phase="PUBLISHING",status="PENDING",actor_id=0)
                db.add(op); db.get(CinemaRoom,show.room_id).operation_id=op.id; db.commit()
            if op.status=="DONE": continue
        with Session(target) as db:
            op=db.get(Operation,op_id)
            if not op.progress.get("bootstrap_closed"):
                clients.close(show_id,1)
                op.progress={**op.progress,"bootstrap_closed":True}; db.commit()
        execute(target,op_id,clients)
        with Session(target) as db:
            op=db.get(Operation,op_id)
            if op.status!="DONE": raise ValueError("Bootstrap publication incomplete: "+op.status)
    return len(ids)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--bootstrap",action="store_true")
    parser.add_argument("--source-host",default="postgres")
    parser.add_argument("--source-port",type=int,default=5432)
    parser.add_argument("--destination-origin",default="http://cinema-service:8086")
    parser.add_argument("--manifest",default="/tmp/cinema-copy-manifest.json")
    args=parser.parse_args(); settings=Settings()
    from .clients import Clients
    with httpx.Client(timeout=5,trust_env=False) as http:
        headers={"X-Service-Key":settings.service_key}
        src_state=http.get(settings.booking_origin+"/internal/v1/sales/migration/ownership",headers=headers)
        dst_state=http.get(args.destination_origin+"/internal/v1/migration/state",headers=headers)
        src_state.raise_for_status(); dst_state.raise_for_status()
        frozen=src_state.json()["owner"]=="maintenance" and not dst_state.json()["writes_enabled"]
        source=create_engine(make_url(os.environ["DATABASE_URL"]).set(host=args.source_host,port=args.source_port))
        target=create_engine(settings.database_url)
        result=transfer(source,target,apply=args.apply,frozen=frozen)
        if args.bootstrap:
            if not args.apply or not frozen: raise ValueError("Bootstrap requires frozen apply")
            result["published"]=bootstrap(source,target,Clients(settings,http))
    Path(args.manifest).write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"verified":result["verified"],"copied":result["copied"],"published":result.get("published"),"rows":{n:i["rows"] for n,i in result["tables"].items()}}))


if __name__=="__main__":
    try: main()
    except Exception as exc:
        print("Cinema migration failed; type="+type(exc).__name__+"; "+str(exc)[:200] if isinstance(exc,ValueError) else "Cinema migration failed; type="+type(exc).__name__)
        raise SystemExit(1)
