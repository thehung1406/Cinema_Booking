from datetime import timedelta
from pathlib import Path
import sys

import pytest
from sqlalchemy import event as sql_event, func, select
from sqlalchemy.orm import Session

from cinema_platform.events import EventEnvelope, OutboxRecord, ReplayAudit, utcnow
from cinema_platform.outbox import enqueue, relay_one, replay

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "services/notification-service/tests"))
from notification_test_support import store  # noqa: E402,F401


def event():
    return EventEnvelope(event_type="ExampleCommitted.v1", producer="test", aggregate_id="test:1", aggregate_version=1, correlation_id="test", data={"value": "immutable"})


def test_rolled_back_outbox_is_never_published_and_unconfirmed_publish_remains_retryable(store):
    value = event()
    with Session(store) as db:
        enqueue(db, value, "public")
        db.rollback()
    assert not relay_one(store, lambda *args: pytest.fail("Uncommitted event published"))
    with Session(store) as db, db.begin():
        enqueue(db, value, "public")
    def fail(*args):
        raise ConnectionError("private AMQP URL")
    relay_one(store, fail, max_attempts=1)
    with Session(store) as db, db.begin():
        row = db.get(OutboxRecord, str(value.event_id))
        assert row.status == "BLOCKED" and row.last_error == "ConnectionError"
        replay(db, row.event_id, "test-operator", "Broker repaired")
    sent = []
    relay_one(store, lambda *args: sent.append(args))
    with Session(store) as db:
        assert db.get(OutboxRecord, str(value.event_id)).status == "PUBLISHED"
        assert db.scalar(select(func.count()).select_from(ReplayAudit)) == 1
    assert len(sent) == 1


def test_publish_confirmed_but_db_commit_lost_replays_same_event_id(store):
    value, published = event(), []
    with Session(store) as db, db.begin():
        enqueue(db, value, "public")
    def broken_commit(session):
        raise RuntimeError("simulate process failure after broker confirm")
    sql_event.listen(Session, "before_commit", broken_commit)
    try:
        with pytest.raises(RuntimeError):
            relay_one(store, lambda destination, event: published.append(str(event.event_id)))
    finally:
        sql_event.remove(Session, "before_commit", broken_commit)
    relay_one(store, lambda destination, event: published.append(str(event.event_id)))
    assert published == [str(value.event_id)] * 2
