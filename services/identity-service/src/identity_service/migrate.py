"""Privileged one-shot copy/verify, never used by the runtime API.

Copies only four allowlisted Identity tables. Refuses to overwrite divergent data.
"""

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import MetaData, Table, create_engine, func, select, text
from sqlalchemy.engine import make_url

from .config import Settings
from .models import Base

TABLES = ("roles", "permissions", "role_permissions", "users")


def canonical(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, (UUID, date, Decimal)):
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
    for name in ("roles", "permissions", "users"):
        max_id = source.execute(select(func.max(Base.metadata.tables[name].c.id))).scalar_one() or 0
        maximum = max(max_id, sequence_value(source, name), sequence_value(destination, name))
        destination.execute(text("SELECT setval(pg_get_serial_sequence(:name, 'id'), :value, :called)"), {"name": name, "value": max(maximum, 1), "called": maximum > 0})


def transfer(source, target, *, apply=False, frozen=False):
    if apply and not frozen:
        raise ValueError("Freeze both application writers before copying")
    if source.url == target.url:
        raise ValueError("Source and target must be separate stores")
    reflected = {name: Table(name, MetaData(), autoload_with=source) for name in TABLES}
    with source.connect().execution_options(isolation_level="REPEATABLE READ") as src, src.begin():
        src.execute(text("SET TRANSACTION READ ONLY"))
        columns = {name: list(t.c.keys()) for name, t in reflected.items()}
        source_summary = snapshot(src, reflected, columns)
        with target.begin() as dst:
            # Serialize copy jobs; runtime writers must also be disabled externally.
            dst.execute(text("SELECT pg_advisory_xact_lock(78433263)"))
            target_summary = snapshot(dst, Base.metadata.tables, columns)
            if apply and dst.execute(text("SELECT count(*) FROM login_sessions")).scalar_one():
                raise ValueError("Destination has sessions; refusing migration after writes")
            if source_summary == target_summary:
                if apply:
                    reseed(src, dst)
                return {"verified": True, "copied": False, "tables": source_summary}
            if not apply:
                raise ValueError("Identity source/target checksums differ")
            if any(item["rows"] for item in target_summary.values()):
                raise ValueError("Destination is not empty or already identical; refusing overwrite")
            for name in TABLES:
                rows = src.execution_options(stream_results=True).execute(select(reflected[name]).order_by(*reflected[name].primary_key.columns)).mappings()
                while batch := rows.fetchmany(500):
                    dst.execute(Base.metadata.tables[name].insert(), [dict(row) for row in batch])
                rows.close()
                src.execution_options(stream_results=False)
            reseed(src, dst)
            copied_summary = snapshot(dst, Base.metadata.tables, columns)
            if copied_summary != source_summary:
                raise ValueError("Post-copy checksum mismatch; destination transaction rolled back")
    return {"verified": True, "copied": True, "tables": source_summary}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--source-host", default="postgres")
    parser.add_argument("--source-port", type=int, default=5432)
    parser.add_argument("--destination-origin", default="http://identity-service:8084")
    parser.add_argument("--manifest", default="/tmp/identity-copy-manifest.json")
    args = parser.parse_args()
    settings = Settings()
    with httpx.Client(timeout=5, trust_env=False) as http:
        headers = {"X-Service-Key": settings.service_key}
        src_state = http.get(settings.read_origin + "/internal/v1/auth/ownership", headers=headers)
        dst_state = http.get(args.destination_origin + "/internal/v1/migration/state", headers=headers)
        src_state.raise_for_status()
        dst_state.raise_for_status()
        frozen = src_state.json()["owner"] == "maintenance" and not dst_state.json()["writes_enabled"]
    source_url = make_url(os.environ["DATABASE_URL"]).set(host=args.source_host, port=args.source_port)
    result = transfer(create_engine(source_url), create_engine(settings.database_url), apply=args.apply, frozen=frozen)
    Path(args.manifest).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verified": result["verified"], "copied": result["copied"], "rows": {name: info["rows"] for name, info in result["tables"].items()}}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Identity migration failed; type=" + type(exc).__name__)
        raise SystemExit(1)
