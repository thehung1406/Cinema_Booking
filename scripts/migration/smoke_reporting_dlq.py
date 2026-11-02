"""Audited local technical DLQ replay of an existing fact; no domain changes."""

import json, os, time
from uuid import uuid4
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from cinema_platform.broker import connect, Publisher
from cinema_platform.events import EventEnvelope, InboxRecord, ReplayAudit
from reporting_service.config import Settings
from reporting_service.models import Projection


def main():
    cfg = Settings()
    engine = create_engine(cfg.database_url)
    connection = connect(os.environ["REPORTING_OPERATOR_AMQP_URL"])
    channel = connection.channel()
    publisher = Publisher(
        os.environ["REPORTING_OPERATOR_AMQP_URL"],
        os.environ["REPORTING_OPERATOR_AMQP_URL"],
    )
    try:
        if channel.queue_declare(
            "reporting.dead.v1", passive=True
        ).method.message_count:
            raise RuntimeError("Inspect existing DLQ cases before a technical drill")
        with Session(engine) as db:
            row = db.scalar(
                select(Projection)
                .where(
                    Projection.source == "catalog",
                    Projection.kind == "film",
                    Projection.deleted.is_(False),
                )
                .order_by(Projection.key)
            )
            if row is None:
                raise RuntimeError("An existing public film fact is required")
            fact = row.fact
            identity = (row.source, row.kind, row.key)
            before = row.sha256
        event = EventEnvelope(
            event_id=uuid4(),
            event_type="ReportFactChanged.v1",
            producer="reporting-source:catalog",
            aggregate_id="catalog:film:" + fact["key"],
            aggregate_version=fact["version"],
            correlation_id="m10-technical-dlq",
            data={"schema_probe": True},
        )
        publisher("public", event)
        deadline = time.monotonic() + 15
        delivery = None
        while time.monotonic() < deadline:
            method, props, body = channel.basic_get("reporting.dead.v1", auto_ack=False)
            if method:
                delivery = (method, props, body)
                break
            time.sleep(0.1)
        if not delivery:
            raise AssertionError("Poison schema did not reach durable DLQ")
        method, props, body = delivery
        if EventEnvelope.model_validate_json(body).event_id != event.event_id:
            channel.basic_nack(method.delivery_tag, requeue=True)
            raise RuntimeError(
                "Another DLQ delivery arrived; leave it for investigation"
            )
        with Session(engine) as db, db.begin():
            db.add(
                ReplayAudit(
                    record_id=str(event.event_id),
                    actor="m10-local-operator",
                    reason="Technical schema recovery: replay unchanged existing public film fact with original event ID",
                )
            )
        corrected = event.model_copy(update={"data": fact})
        publisher("public", corrected)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with Session(engine) as db:
                if db.get(InboxRecord, ("reporting.facts.v1", str(event.event_id))):
                    assert db.get(Projection, identity).sha256 == before
                    break
            time.sleep(0.1)
        else:
            raise AssertionError("Corrected delivery was not committed")
        channel.basic_ack(method.delivery_tag)
        publisher("public", corrected)
        result = dict(
            poison_dlq=True,
            audited_original_event_id_replay=True,
            existing_fact_unchanged=True,
        )
        print(json.dumps(result))
    finally:
        publisher.close()
        connection.close()
        engine.dispose()


if __name__ == "__main__":
    main()
