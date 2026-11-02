"""Transactional dirty revisions -> full replacement facts -> own public outbox.

Each runtime connects only to its own database. No timestamp/MAX(id) cursor is
used: dirty keys persist across outages and snapshots overlap versioned events.
"""

import argparse, hashlib, json, os, time
from datetime import datetime, timezone
from secrets import compare_digest
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from .events import EventEnvelope, OutboxRecord
from .outbox import enqueue, relay_one
from .broker import Publisher
from .logging import service_logger


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(pattern="^(booking|payment|catalog|cinema|review)$")
    generation: UUID
    kind: str = Field(pattern="^[a-z_]{1,30}$")
    key: str = Field(min_length=1, max_length=100)
    version: int = Field(gt=0)
    changed_at: AwareDatetime
    deleted: bool
    payload: dict


class Checkpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(pattern="^(booking|payment|catalog|cinema|review)$")
    generation: UUID
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    count: int = Field(ge=0)
    as_of: AwareDatetime


def wire(source, generation, row):
    return Fact(source=source, generation=generation, **dict(row)).model_dump(
        mode="json"
    )


def digest_facts(rows):
    return hashlib.sha256(
        b"".join(
            (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
            for row in rows
        )
    ).hexdigest()


def checkpoint(engine, source):
    with Session(engine) as db, db.begin():
        row = (
            db.execute(text("SELECT * FROM report_source_state WHERE id=1 FOR UPDATE"))
            .mappings()
            .one()
        )
        if db.execute(
            text(
                "SELECT count(*) FROM outbox_events WHERE event_type='ReportFactChanged.v1' AND status<>'PUBLISHED'"
            )
        ).scalar_one():
            return False
        if db.execute(
            text(
                "SELECT count(*) FROM report_dirty d LEFT JOIN report_source_facts f USING(kind,key) WHERE f.version IS NULL OR d.version>f.version"
            )
        ).scalar_one():
            return False
        data = [
            wire(source, row["generation"], fact)
            for fact in db.execute(
                text("SELECT * FROM report_source_facts ORDER BY kind,key")
            ).mappings()
        ]
        version = row["checkpoint"] + 1
        stamp = datetime.now(timezone.utc)
        db.execute(
            text("UPDATE report_source_state SET checkpoint=:version WHERE id=1"),
            {"version": version},
        )
        enqueue(
            db,
            EventEnvelope(
                event_type="ReportCheckpoint.v1",
                producer="reporting-source:" + source,
                aggregate_id=source + ":checkpoint",
                aggregate_version=version,
                correlation_id="reporting:" + source,
                data=dict(
                    source=source,
                    generation=str(row["generation"]),
                    sha256=digest_facts(data),
                    count=len(data),
                    as_of=stamp.isoformat(),
                ),
            ),
            "public",
        )
        return True


def materialize(engine, source, limit=500):
    """No locks on business rows. Per-key dirty row lock serializes only the feed.

    A concurrent business write either commits before this lock (included now),
    or increments the dirty revision after we commit (included next time).
    Intermediate revisions may coalesce: every event is a complete replacement.
    """
    with Session(engine) as db, db.begin():
        generation = db.execute(
            text("SELECT generation FROM report_source_state WHERE id=1")
        ).scalar_one()
        # Also covers a privileged historical import performed with user triggers disabled.
        db.execute(
            text(
                """INSERT INTO report_dirty(kind,key) SELECT e.kind,e.key FROM reporting_export e
            LEFT JOIN report_source_facts f USING(kind,key) WHERE f.key IS NULL ON CONFLICT DO NOTHING"""
            )
        )
        dirty = (
            db.execute(
                text(
                    """SELECT d.* FROM report_dirty d LEFT JOIN report_source_facts f USING(kind,key)
            WHERE f.version IS NULL OR d.version>f.version ORDER BY d.kind,d.key
            LIMIT :limit FOR UPDATE OF d SKIP LOCKED"""
                ),
                {"limit": limit},
            )
            .mappings()
            .all()
        )
        for item in dirty:
            payload = db.execute(
                text(
                    "SELECT payload FROM reporting_export WHERE kind=:kind AND key=:key"
                ),
                dict(item),
            ).scalar_one_or_none()
            values = {
                **dict(item),
                "deleted": payload is None,
                "payload": payload or {},
            }
            db.execute(
                text(
                    """INSERT INTO report_source_facts(kind,key,version,changed_at,deleted,payload)
                VALUES (:kind,:key,:version,:changed_at,:deleted,CAST(:body AS jsonb))
                ON CONFLICT(kind,key) DO UPDATE SET version=EXCLUDED.version,changed_at=EXCLUDED.changed_at,
                deleted=EXCLUDED.deleted,payload=EXCLUDED.payload"""
                ),
                {**values, "body": json.dumps(values["payload"])},
            )
            data = wire(source, generation, values)
            event = EventEnvelope(
                event_id=uuid5(
                    NAMESPACE_URL,
                    f'report:{generation}:{item["kind"]}:{item["key"]}:{item["version"]}',
                ),
                event_type="ReportFactChanged.v1",
                occurred_at=item["changed_at"],
                producer="reporting-source:" + source,
                aggregate_id=f'{source}:{item["kind"]}:{item["key"]}',
                aggregate_version=item["version"],
                correlation_id="reporting:" + source,
                data=data,
            )
            enqueue(db, event, "public")
        return len(dirty)


def snapshot(engine, source):
    while materialize(engine, source):
        pass
    sid = uuid4()
    stamp = datetime.now(timezone.utc)
    with engine.connect().execution_options(
        isolation_level="REPEATABLE READ"
    ) as conn, conn.begin():
        generation = conn.execute(
            text("SELECT generation FROM report_source_state WHERE id=1")
        ).scalar_one()
        rows = (
            conn.execute(text("SELECT * FROM report_source_facts ORDER BY kind,key"))
            .mappings()
            .all()
        )
        data = [wire(source, generation, row) for row in rows]
        digest = digest_facts(data)
        conn.execute(
            text(
                "INSERT INTO report_snapshots VALUES (:id,:generation,:stamp,:count,:sha)"
            ),
            dict(
                id=sid, generation=generation, stamp=stamp, count=len(data), sha=digest
            ),
        )
        for start in range(0, len(data), 500):
            conn.execute(
                text(
                    "INSERT INTO report_snapshot_rows VALUES (:id,:ordinal,CAST(:fact AS jsonb))"
                ),
                [
                    dict(id=sid, ordinal=i, fact=json.dumps(data[i]))
                    for i in range(start, min(start + 500, len(data)))
                ],
            )
    return dict(
        snapshot_id=str(sid),
        source=source,
        generation=str(generation),
        as_of=stamp.isoformat(),
        count=len(data),
        sha256=digest,
    )


def source_router(engine, key, source):
    def private(x_service_key: str = Header(default="")):
        if len(key) < 32:
            raise HTTPException(503, "Reporting export credential missing")
        if not compare_digest(key.encode(), x_service_key.encode()):
            raise HTTPException(401, "Invalid service credential")

    from fastapi import Depends

    router = APIRouter(
        prefix="/internal/v1/reporting",
        dependencies=[Depends(private)],
        include_in_schema=False,
    )

    @router.post("/snapshots")
    def create():
        return snapshot(engine, source)

    @router.get("/snapshots/{snapshot_id}")
    def page(
        snapshot_id: UUID,
        after: int = Query(-1, ge=-1),
        limit: int = Query(250, ge=1, le=500),
    ):
        with engine.connect() as conn:
            if not conn.execute(
                text("SELECT 1 FROM report_snapshots WHERE id=:id"), {"id": snapshot_id}
            ).scalar():
                raise HTTPException(404, "Snapshot not found")
            rows = (
                conn.execute(
                    text(
                        "SELECT ordinal,fact FROM report_snapshot_rows WHERE snapshot_id=:id AND ordinal>:after ORDER BY ordinal LIMIT :limit"
                    ),
                    dict(id=snapshot_id, after=after, limit=limit),
                )
                .mappings()
                .all()
            )
            return dict(
                items=[r["fact"] for r in rows],
                next_cursor=rows[-1]["ordinal"] if rows else after,
            )

    @router.get("/state")
    def state():
        with engine.connect() as conn:
            return dict(
                generation=str(
                    conn.execute(
                        text("SELECT generation FROM report_source_state WHERE id=1")
                    ).scalar_one()
                ),
                pending=conn.execute(
                    text(
                        "SELECT count(*) FROM report_dirty d LEFT JOIN report_source_facts f USING(kind,key) WHERE f.version IS NULL OR d.version>f.version"
                    )
                ).scalar_one(),
            )

    return router


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        required=True,
        choices=["booking", "payment", "catalog", "cinema", "review"],
    )
    args = parser.parse_args()
    engine = create_engine(os.environ["REPORT_SOURCE_DATABASE_URL"], pool_pre_ping=True)
    publisher = Publisher(
        os.environ["REPORT_SOURCE_AMQP_URL"], os.environ["REPORT_SOURCE_AMQP_URL"]
    )
    log = service_logger("report-source-" + args.source)
    last_checkpoint = 0
    while True:
        try:
            materialize(engine, args.source)
            if time.monotonic() - last_checkpoint >= 10:
                checkpoint(engine, args.source)
                last_checkpoint = time.monotonic()
            for _ in range(100):
                if not relay_one(
                    engine,
                    publisher,
                    event_types=["ReportFactChanged.v1", "ReportCheckpoint.v1"],
                ):
                    break
        except Exception as exc:
            publisher.close()
            log.warning("capture deferred type=%s", type(exc).__name__)
        time.sleep(1)


if __name__ == "__main__":
    main()
