from datetime import datetime, timezone, date, timedelta
from uuid import uuid4
import hashlib, json, os, time
import httpx, pika, pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, event
from sqlalchemy.orm import Session
from cinema_platform.reporting import (
    Fact,
    materialize,
    snapshot,
    source_router,
    checkpoint,
    digest_facts,
)
from cinema_platform.events import EventEnvelope, OutboxRecord, InboxRecord
from cinema_platform.broker import Publisher, connect
from reporting_service.models import Projection, SourceState
from reporting_service.projection import apply, receive, source_digest
from reporting_service.config import Settings, SOURCES
from reporting_service.main import create_app, Filters
from reporting_service.reports import report
from reporting_service.bootstrap import bootstrap
from test_saga import new_order, capture, deliver
from booking_service import facts as booking_facts
from booking_service.models import Booking

KEY = "isolated-internal-service-key-32-characters-test-only"


def seed(db):
    generations = {s: uuid4() for s in SOURCES}
    stamp = datetime.now(timezone.utc)

    def put(source, kind, key, payload):
        apply(
            db,
            Fact(
                source=source,
                generation=generations[source],
                kind=kind,
                key=str(key),
                version=1,
                changed_at=stamp,
                deleted=False,
                payload=payload,
            ),
        )

    put("catalog", "film", 1, dict(id=1, title="=Safe film", retired=False))
    for version, seats in [(1, [1, 2, 3]), (2, [1, 2])]:
        put(
            "booking",
            "config",
            f"10:{version}",
            dict(
                showtime_id=10,
                sales_version=version,
                film_id=1,
                theater_id=2,
                show_date="2026-11-02",
                status="ACTIVE",
                active_seat_ids=seats,
            ),
        )
    put("booking", "gate", 10, dict(showtime_id=10, sales_version=2))
    put("booking", "booked_seats", 10, dict(showtime_id=10, seat_ids=[1, 3]))
    put(
        "booking",
        "booking",
        1,
        dict(
            id=1,
            showtime_id=10,
            sales_version=1,
            total_amount="185000.00",
            booking_status="CONFIRMED",
            payment_status="PAID",
            accepted_payment_id=1,
            accepted_checkout_version=1,
            seats=[
                dict(seat_id=1, valid_ticket=True),
                dict(seat_id=3, valid_ticket=True),
            ],
        ),
    )
    for pid in [1, 2]:
        put(
            "payment",
            "payment",
            pid,
            dict(
                id=pid,
                booking_id=1,
                checkout_version=1,
                amount="185000.00",
                currency="VND",
                status="PAID",
            ),
        )
    for rid, version, label, status, updated in [
        (1, 1, "positive", "succeeded", "2026-11-01T17:00:00+00:00"),
        (2, 0, "negative", "succeeded", "2026-11-02T16:59:59+00:00"),
        (3, 1, "neutral", "succeeded", "2026-11-02T17:00:00+00:00"),
    ]:
        put(
            "review",
            "review",
            rid,
            dict(
                id=rid,
                film_id=1,
                updated_at=updated,
                content_version=1,
                is_deleted=False,
                moderation_status="approved",
                sentiment_version=version,
                sentiment_status=status,
                label=label,
                model_version="test",
            ),
        )
    for source in SOURCES:
        state = db.get(SourceState, source)
        if state is None:
            state = SourceState(source=source, generation=str(generations[source]))
            db.add(state)
        state.bootstrapped = True
        state.snapshot_at = stamp
        state.verified_at = stamp
    db.commit()
    return generations


def test_report_semantics_food_total_not_attempts_active_slots_and_vietnam_review_window(
    reporting_store, monkeypatch
):
    import reporting_service.reports as reports

    monkeypatch.setattr(
        reports, "now", lambda: datetime(2026, 11, 3, tzinfo=timezone.utc)
    )
    with Session(reporting_store) as db:
        seed(db)
        result = report(
            db, Filters(start_date=date(2026, 11, 2), end_date=date(2026, 11, 2))
        )
        assert (
            result["revenue"] == 185000
            and result["booking_count"] == 1
            and result["ticket_count"] == 2
        )
        assert (
            result["seat_slots"] == 2
            and result["occupied_seats"] == 1
            and result["occupancy"] == 50
        )
        assert result["sentiments"] == dict(
            positive=1, neutral=0, negative=0, total=2, pending=1, coverage=50.0
        )
        assert (
            report(
                db,
                Filters(
                    start_date=date(2026, 11, 2),
                    end_date=date(2026, 11, 2),
                    theater_id=99,
                ),
            )["sentiments"]["total"]
            == 0
        )


def test_revisions_tombstones_conflicts_generation_and_inbox_commit(reporting_store):
    stamp = datetime.now(timezone.utc)
    gen = uuid4()

    def fact(version, deleted=False):
        return Fact(
            source="catalog",
            generation=gen,
            kind="film",
            key="1",
            version=version,
            changed_at=stamp,
            deleted=deleted,
            payload={} if deleted else dict(id=1, title=str(version)),
        )

    def envelope(value):
        return EventEnvelope(
            event_type="ReportFactChanged.v1",
            producer="reporting-source:catalog",
            aggregate_id="catalog:film:1",
            aggregate_version=value.version,
            data=value.model_dump(mode="json"),
            correlation_id="test",
        )

    event = envelope(fact(2))
    with Session(reporting_store) as db, db.begin():
        assert receive(db, event)
    with Session(reporting_store) as db, db.begin():
        assert receive(db, event) is False
        assert apply(db, fact(1)) == "old"
    with pytest.raises(ValueError):
        with Session(reporting_store) as db, db.begin():
            apply(
                db, fact(2).model_copy(update={"payload": dict(id=1, title="conflict")})
            )
    with Session(reporting_store) as db, db.begin():
        apply(db, fact(4, True))
        assert apply(db, fact(3)) == "old"
    with pytest.raises(ValueError):
        with Session(reporting_store) as db, db.begin():
            apply(db, fact(5).model_copy(update={"generation": uuid4()}))
    with Session(reporting_store) as db:
        assert db.get(Projection, ("catalog", "film", "1")).deleted


def test_real_source_snapshot_overlap_stream_and_historical_report_equivalence(
    pair, reporting_store
):
    bid = new_order(pair)
    capture(pair, bid)
    deliver(pair)
    # API snapshots use real source views and frozen capture triggers, no foreign DB in Reporting.
    cfg = Settings(service_key=KEY)
    clients = {"booking": pair.bc, "payment": pair.pc}

    def transport(req):
        source = next(
            k
            for k, v in cfg.source_origins.items()
            if req.url.host == httpx.URL(v).host
        )
        response = clients[source].request(
            req.method, req.url.raw_path.decode(), headers={"X-Service-Key": KEY}
        )
        return httpx.Response(response.status_code, json=response.json())

    with httpx.Client(transport=httpx.MockTransport(transport)) as http:
        for source in ["booking", "payment"]:
            assert bootstrap(reporting_store, cfg, source, http)["verified"]
    # A queued event older/equal to snapshot cannot double count or overwrite it.
    for engine in [pair.book, pair.pay]:
        with Session(engine) as db:
            events = [
                EventEnvelope.model_validate(o.payload)
                for o in db.scalars(
                    select(OutboxRecord).where(
                        OutboxRecord.event_type == "ReportFactChanged.v1"
                    )
                )
            ]
        for value in reversed(events):
            with Session(reporting_store) as db, db.begin():
                receive(db, value)
    with Session(pair.book) as db:
        old = booking_facts.report(db, date.today(), date.today() + timedelta(days=10))
    with Session(reporting_store) as db:
        for source in ["catalog", "review", "cinema"]:
            db.add(
                SourceState(
                    source=source,
                    generation=str(uuid4()),
                    bootstrapped=True,
                    snapshot_at=datetime.now(timezone.utc),
                )
            )
        film_id = old["by_film"][0]["film_id"]
        gen = db.get(SourceState, "catalog").generation
        apply(
            db,
            Fact(
                source="catalog",
                generation=gen,
                kind="film",
                key=str(film_id),
                version=1,
                changed_at=datetime.now(timezone.utc),
                deleted=False,
                payload=dict(id=film_id, title="Independent film"),
            ),
        )
        db.commit()
        result = report(
            db,
            Filters(
                start_date=date.today(), end_date=date.today() + timedelta(days=10)
            ),
        )
        for key in [
            "revenue",
            "booking_count",
            "ticket_count",
            "seat_slots",
            "occupied_seats",
            "occupancy",
        ]:
            assert result[key] == old[key], key
    # A rollback changes neither the domain fact nor its dirty revision.
    with pair.book.connect() as conn:
        before = conn.execute(
            text("SELECT version FROM report_dirty WHERE kind='booking' AND key=:id"),
            {"id": str(bid)},
        ).scalar_one()
    with Session(pair.book) as db:
        db.get(Booking, bid).payment_status = "FAILED"
        db.flush()
        db.rollback()
    with pair.book.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT version FROM report_dirty WHERE kind='booking' AND key=:id"
                ),
                {"id": str(bid)},
            ).scalar_one()
            == before
        )


def test_report_api_auth_csv_and_stale_watermarks_without_source_http(reporting_store):
    with Session(reporting_store) as db:
        seed(db)
    user = dict(user_id=1, role="ADMIN", is_active=True, permissions=[])
    cfg = Settings(service_key=KEY)
    with TestClient(
        create_app(
            cfg,
            engine=reporting_store,
            auth_transport=httpx.MockTransport(
                lambda req: httpx.Response(200, json=user)
            ),
        )
    ) as api:
        path = "/admin/reports?start_date=2026-11-02&end_date=2026-11-02"
        assert api.get(path).status_code == 401
        assert (
            api.get(path, headers={"Authorization": "Bearer test"}).status_code == 403
        )
        user["permissions"] = ["reports.view"]
        headers = {"Authorization": "Bearer test"}
        r = api.get(path, headers=headers)
        assert r.status_code == 200, r.text
        assert set(r.json()["watermarks"]) == set(SOURCES)
        assert (
            api.get(
                "/admin/reports?start_date=2026-11-02&end_date=2026-01-01",
                headers=headers,
            ).status_code
            == 422
        )
        csv = api.get(path.replace("/reports?", "/reports.csv?"), headers=headers)
        assert csv.status_code == 200 and "'=Safe film" in csv.text
        assert api.get("/health/ready").status_code == 200


def test_real_reporting_transport_redelivery_and_owner_topic_permissions(
    reporting_store,
):
    with Session(reporting_store) as db:
        gens = seed(db)
        fact = db.get(Projection, ("booking", "booking", "1")).fact
    fact = {
        **fact,
        "version": 2,
        "payload": {**fact["payload"], "booking_status": "CANCELLED"},
    }
    envelope = EventEnvelope(
        event_type="ReportFactChanged.v1",
        producer="reporting-source:booking",
        aggregate_id="booking:booking:1",
        aggregate_version=2,
        correlation_id="test",
        data=fact,
    )
    operator = connect(os.environ["TEST_AMQP_OPERATOR_PUBLIC"])
    channel = operator.channel()
    channel.queue_purge("reporting.bootstrap.v1")
    publisher = Publisher(
        os.environ["TEST_AMQP_REPORTING_BOOKING"],
        os.environ["TEST_AMQP_REPORTING_BOOKING"],
    )
    try:
        publisher("public", envelope)
        method, _, body = channel.basic_get("reporting.bootstrap.v1", auto_ack=False)
        assert method
        with Session(reporting_store) as db, db.begin():
            assert receive(db, EventEnvelope.model_validate_json(body))
        channel.close()
        channel = operator.channel()
        method, _, body = channel.basic_get("reporting.bootstrap.v1", auto_ack=False)
        assert method.redelivered
        with Session(reporting_store) as db, db.begin():
            assert receive(db, EventEnvelope.model_validate_json(body)) is False
        channel.basic_ack(method.delivery_tag)
        with pytest.raises(pika.exceptions.ChannelClosedByBroker):
            publisher(
                "public",
                envelope.model_copy(update={"producer": "reporting-source:payment"}),
            )
        with Session(reporting_store) as db:
            assert (
                db.get(Projection, ("booking", "booking", "1")).fact["payload"][
                    "booking_status"
                ]
                == "CANCELLED"
            )
    finally:
        publisher.close()
        operator.close()


def test_checkpoint_digest_detects_missing_entity_instead_of_claiming_freshness(
    reporting_store,
):
    with Session(reporting_store) as db:
        gens = seed(db)
    event = EventEnvelope(
        event_type="ReportCheckpoint.v1",
        producer="reporting-source:booking",
        aggregate_id="booking:checkpoint",
        aggregate_version=1,
        correlation_id="test",
        data=dict(
            source="booking",
            generation=str(gens["booking"]),
            sha256="0" * 64,
            count=0,
            as_of=datetime.now(timezone.utc).isoformat(),
        ),
    )
    with Session(reporting_store) as db, db.begin():
        receive(db, event)
    with Session(reporting_store) as db:
        assert db.get(SourceState, "booking").verified_at is None


def test_direct_ai_review_adapters_remain_functional_without_legacy(monkeypatch):
    from ai_service.read_client import ReadSession
    from ai_service.config import Settings as AISettings
    from ai_service.schemas import ToolContext, ToolCall
    from review_service.read_client import ReadClient
    from review_service.config import Settings as ReviewSettings

    hosts = []

    def transport(req):
        hosts.append(req.url.host)
        assert req.url.host != "fastapi"
        path = req.url.path
        if path.endswith("/films/batch"):
            return httpx.Response(200, json=[dict(id=1, title="Phim", image=None)])
        if path.endswith("/theaters/matches") or path.endswith("/films/matches"):
            return httpx.Response(
                200, json=[dict(id=1, name="Phim" if "/films/" in path else "Rạp")]
            )
        if path == "/theaters/1":
            return httpx.Response(200, json=dict(id=1, name="Rạp"))
        if path.endswith("/context"):
            return httpx.Response(200, json=dict(valid=True))
        if path.endswith("/tool"):
            return httpx.Response(
                200,
                json=[
                    dict(
                        id="seats:1",
                        title="Ghế trống",
                        text="2/2",
                        url="/seat-selection/1",
                        kind="live",
                    )
                ],
            )
        if path.endswith("/profiles"):
            return httpx.Response(200, json=[dict(id=1, username="Khán giả")])
        if path.endswith("/verified"):
            return httpx.Response(
                200, json=[dict(user_id=1, film_id=1, verified_purchase=True)]
            )
        if path.endswith("/candidates"):
            return httpx.Response(200, json=[1])
        raise AssertionError(path)

    with httpx.Client(transport=httpx.MockTransport(transport)) as http:
        ai = ReadSession(
            http,
            AISettings(
                database_url="sqlite://",
                redis_url="redis://localhost",
                service_key=KEY,
                direct_reads_enabled=True,
            ),
        )
        assert ai.matches("Phim Rạp").film_id[0].id == 1
        assert ai.names(ToolContext(film_id=1, theater_id=1)).film_name == "Phim"
        assert (
            ai.run(
                ToolCall(
                    name="get_seat_availability", context=ToolContext(showtime_id=1)
                ),
                False,
            )[0]["url"]
            == "/seat-selection/1"
        )
        review = ReadClient(
            http,
            ReviewSettings(
                database_url="sqlite://",
                identity_origin="http://identity-service:8084",
                service_key=KEY,
                direct_reads_enabled=True,
            ),
        )
        from types import SimpleNamespace

        assert review.authors([SimpleNamespace(user_id=1, film_id=1)])[
            (1, 1)
        ].verified_purchase
        assert review.candidates()[0].id == 1
    assert set(hosts) == {
        "catalog-service",
        "cinema-service",
        "booking-service",
        "identity-service",
    }


def test_reporting_auth_outage_fails_closed_with_projection_unchanged(reporting_store):
    with Session(reporting_store) as db:
        seed(db)
    cfg = Settings(service_key=KEY)
    with TestClient(
        create_app(
            cfg,
            engine=reporting_store,
            auth_transport=httpx.MockTransport(lambda req: httpx.Response(503)),
        )
    ) as api:
        response = api.get(
            "/admin/reports?start_date=2026-11-02&end_date=2026-11-02",
            headers={"Authorization": "Bearer test"},
        )
        assert response.status_code == 503
        assert api.get("/health/ready").status_code == 200
    with Session(reporting_store) as db:
        assert (
            db.get(Projection, ("booking", "booking", "1")).fact["payload"][
                "booking_status"
            ]
            == "CONFIRMED"
        )
