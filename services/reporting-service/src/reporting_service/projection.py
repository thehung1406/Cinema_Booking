from datetime import datetime
from sqlalchemy import select, text
from cinema_platform.events import fingerprint
from cinema_platform.consume import once
from cinema_platform.reporting import Fact, Checkpoint, digest_facts
from .models import Projection, SourceState, now
from .config import SOURCES


def source_state(db, source, generation):
    if source not in SOURCES:
        raise ValueError("Unknown source")
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:source,18))"),
        {"source": source},
    )
    row = db.get(SourceState, source)
    if row and row.generation != str(generation):
        raise ValueError(
            "Source generation changed; freeze and reconcile restore first"
        )
    if not row:
        row = SourceState(source=source, generation=str(generation))
        db.add(row)
        db.flush()
    return row


def apply(db, value):
    fact = Fact.model_validate(value)
    state = source_state(db, fact.source, fact.generation)
    key = (fact.source, fact.kind, fact.key)
    old = db.get(Projection, key)
    payload = fact.model_dump(mode="json")
    sha = fingerprint(payload)
    if old and old.version > fact.version:
        return "old"
    if old and old.version == fact.version:
        if old.sha256 != sha:
            raise ValueError("Conflicting entity version")
        return "duplicate"
    if not old:
        old = Projection(source=fact.source, kind=fact.kind, key=fact.key)
        db.add(old)
    old.version = fact.version
    old.deleted = fact.deleted
    old.fact = payload
    old.sha256 = sha
    old.received_at = now()
    # A replacement may be ahead of another key from the same owner transaction.
    # Do not claim current-source freshness until its full checkpoint digest agrees.
    state.verified_at = None
    state.observed_at = now()
    db.flush()
    return "applied"


def source_digest(db, source):
    rows = list(
        db.scalars(
            select(Projection)
            .where(Projection.source == source)
            .order_by(Projection.kind, Projection.key)
        )
    )
    return len(rows), digest_facts([row.fact for row in rows])


def receive(db, event):
    if event.event_type == "ReportFactChanged.v1":
        fact = Fact.model_validate(event.data)
        if (
            event.producer != "reporting-source:" + fact.source
            or event.aggregate_id != f"{fact.source}:{fact.kind}:{fact.key}"
            or event.aggregate_version != fact.version
        ):
            raise ValueError("Invalid report aggregate")
        return once(db, "reporting.facts.v1", event, lambda: apply(db, fact))
    if event.event_type != "ReportCheckpoint.v1":
        if event.event_type not in {
            "BookingConfirmed.v1",
            "CheckoutCreated.v1",
            "BookingExpired.v1",
            "PaymentCaptured.v1",
            "PaymentBookingResult.v1",
            "ReviewChanged.v1",
            "ReviewSentimentUpdated.v1",
        }:
            raise ValueError("Unsupported reporting event")
        from .reports import readiness

        if not readiness(db):
            raise RuntimeError("Bootstrap must cover legacy business events before ACK")
        return once(db, "reporting.legacy-audit.v1", event, lambda: None)
    data = Checkpoint.model_validate(event.data).model_dump(mode="json")
    if (
        event.producer != "reporting-source:" + data["source"]
        or event.aggregate_id != data["source"] + ":checkpoint"
    ):
        raise ValueError("Invalid report checkpoint")

    def update():
        state = source_state(db, data["source"], data["generation"])
        if event.aggregate_version <= state.checkpoint_version:
            return
        count, digest = source_digest(db, data["source"])
        state.checkpoint_version = event.aggregate_version
        state.checkpoint_at = datetime.fromisoformat(data["as_of"])
        state.verified_at = (
            state.checkpoint_at
            if (count, digest) == (data["count"], data["sha256"])
            else None
        )
        state.observed_at = now()

    return once(db, "reporting.facts.v1", event, update)
