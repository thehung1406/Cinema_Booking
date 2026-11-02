"""Explicit local acceptance benchmark; not part of timing-sensitive CI tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from statistics import median
from threading import Barrier
from time import perf_counter, sleep, monotonic
from uuid import uuid4
import json, os, subprocess, sys
import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlmodel import Session
from cinema_platform.events import fingerprint
from cinema_platform.reporting import Fact
from cinema_platform.broker import Publisher, connect
from cinema_platform.outbox import relay_one
from reporting_service.models import Projection, SourceState
from reporting_service.config import Settings, SOURCES
from reporting_service.main import create_app
from booking_service import reservations, bookings, sales
from booking_service.schemas.sales import SalesSnapshot
from booking_service.schemas.booking import BookingCreateRequest
from payment_service.models import Fulfillment
from test_saga import signed, start


def summary(values):
    values = sorted(values)
    return dict(
        count=len(values),
        p50_ms=round(median(values), 2),
        p95_ms=round(values[min(len(values) - 1, int(len(values) * 0.95))], 2),
        max_ms=round(max(values), 2),
    )


def test_local_report_contention_and_broker_confirmation_baseline(
    pair, reporting_store
):
    result = {}
    gate = Barrier(16)

    def contend(i):
        with Session(pair.book) as db:
            gate.wait(timeout=15)
            begin = perf_counter()
            try:
                reservations.hold(db, 1, [1, 2], i + 100)
                outcome = "held"
            except HTTPException as exc:
                db.rollback()
                assert exc.status_code == 409
                outcome = "conflict"
            return outcome, (perf_counter() - begin) * 1000

    with ThreadPoolExecutor(16) as pool:
        holds = list(pool.map(contend, range(16)))
    assert [x[0] for x in holds].count("held") == 1
    result["seat_contention"] = {
        **summary([x[1] for x in holds]),
        "winners": 1,
        "conflicts": 15,
    }
    with Session(pair.book) as db:
        from booking_service.models import Reservation

        r = db.scalar(select(Reservation).where(Reservation.status == "ACTIVE"))
        reservations.release(db, 1, [1, 2], r.user_id, r.id)
        template = sales.configuration(db, 1).snapshot
    operator = connect(os.environ["TEST_AMQP_OPERATOR_PUBLIC"])
    channel = operator.channel()
    for q in ["booking.payment.v1", "payment.booking.v1"]:
        channel.queue_purge(q)
    operator.close()
    env = {
        **os.environ,
        "BOOKING_WRITES_ENABLED": "true",
        "PAYMENT_WRITES_ENABLED": "true",
    }
    processes = [
        subprocess.Popen(
            [sys.executable, "-m", module],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for module in ["booking_service.payment_consumer", "payment_service.worker"]
    ]
    pp = Publisher(
        os.environ["PAYMENT_AMQP_PUBLIC_URL"], os.environ["PAYMENT_AMQP_PUBLIC_URL"]
    )
    bp = Publisher(os.environ["AMQP_PUBLIC_URL"], os.environ["AMQP_NOTIFICATION_URL"])
    times = []
    try:
        for show in range(2, 10):
            cfg = SalesSnapshot.model_validate(
                {**template, "showtime_id": show, "catalog_binding_id": str(uuid4())}
            )
            with Session(pair.book) as db:
                sales.close(db, show, 1)
                sales.install(db, cfg, cfg.digest(), 2)
                sales.open_sales(db, show, 1, cfg.digest(), 3)
                rid = reservations.hold(db, show, [1, 2], 1)[0]["reservation_id"]
                bid = bookings.create(
                    db,
                    BookingCreateRequest(
                        userId=1,
                        showtimeId=show,
                        totalAmount="150000",
                        paymentMethod="Online",
                        reservationId=rid,
                        seats=[dict(seat_id=i, price=75000) for i in [1, 2]],
                    ),
                    1,
                    uuid4().hex,
                )["bookingId"]
            body = signed(pair, start(pair, bid))
            begin = perf_counter()
            assert (
                pair.pc.post("/payment/vnpay-ipn", json=body).json()["RspCode"] == "00"
            )
            deadline = monotonic() + 15
            while monotonic() < deadline:
                relay_one(pair.pay, pp, event_types=["PaymentCaptured.v1"])
                relay_one(pair.book, bp, event_types=["PaymentBookingResult.v1"])
                with Session(pair.pay) as db:
                    row = db.scalar(
                        select(Fulfillment).order_by(Fulfillment.payment_id.desc())
                    )
                    if row and row.outcome == "CONFIRMED":
                        break
                sleep(0.02)
            else:
                raise AssertionError("Confirmation timeout")
            times.append((perf_counter() - begin) * 1000)
        result["provider_receipt_to_booking_ack"] = summary(times)
    finally:
        for process in processes:
            process.terminate()
            process.wait(timeout=10)
        pp.close()
        bp.close()
    stamp = datetime.now(timezone.utc)
    generations = {s: uuid4() for s in SOURCES}
    rows = []

    def put(source, kind, key, payload):
        fact = Fact(
            source=source,
            generation=generations[source],
            kind=kind,
            key=str(key),
            version=1,
            changed_at=stamp,
            deleted=False,
            payload=payload,
        ).model_dump(mode="json")
        rows.append(
            dict(
                source=source,
                kind=kind,
                key=str(key),
                version=1,
                deleted=False,
                fact=fact,
                sha256=fingerprint(fact),
                received_at=stamp,
            )
        )

    put("catalog", "film", 1, dict(id=1, title="Synthetic benchmark film"))
    put(
        "booking",
        "config",
        "10:1",
        dict(
            showtime_id=10,
            sales_version=1,
            film_id=1,
            theater_id=1,
            show_date=date.today().isoformat(),
            status="ACTIVE",
            active_seat_ids=list(range(1, 2001)),
        ),
    )
    put("booking", "gate", 10, dict(showtime_id=10, sales_version=1))
    put(
        "booking",
        "booked_seats",
        10,
        dict(showtime_id=10, seat_ids=list(range(1, 2001))),
    )
    for i in range(1, 1001):
        put(
            "booking",
            "booking",
            i,
            dict(
                id=i,
                showtime_id=10,
                sales_version=1,
                total_amount="150000.00",
                booking_status="CONFIRMED",
                payment_status="PAID",
                accepted_payment_id=i,
                accepted_checkout_version=1,
                seats=[
                    dict(seat_id=2 * i - 1, valid_ticket=True),
                    dict(seat_id=2 * i, valid_ticket=True),
                ],
            ),
        )
        put(
            "payment",
            "payment",
            i,
            dict(
                id=i,
                booking_id=i,
                checkout_version=1,
                amount="150000.00",
                currency="VND",
                status="PAID",
            ),
        )
    with reporting_store.begin() as conn:
        conn.execute(Projection.__table__.insert(), rows)
        conn.execute(
            SourceState.__table__.insert(),
            [
                dict(
                    source=s,
                    generation=str(generations[s]),
                    bootstrapped=True,
                    snapshot_at=stamp,
                    verified_at=stamp,
                )
                for s in SOURCES
            ],
        )
    cfg = Settings(service_key="isolated-internal-service-key-32-characters-test-only")
    app = create_app(
        cfg,
        engine=reporting_store,
        auth_transport=httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json=dict(
                    user_id=1,
                    role="ADMIN",
                    is_active=True,
                    permissions=["reports.view"],
                ),
            )
        ),
    )
    with TestClient(app) as api:

        def read(_):
            begin = perf_counter()
            r = api.get(
                "/admin/reports",
                params=dict(
                    start_date=date.today().isoformat(),
                    end_date=date.today().isoformat(),
                ),
                headers={"Authorization": "Bearer benchmark-token"},
            )
            assert r.status_code == 200, r.text
            assert (
                r.json()["booking_count"] == 1000 and r.json()["ticket_count"] == 2000
            )
            return (perf_counter() - begin) * 1000

        begin = perf_counter()
        with ThreadPoolExecutor(8) as pool:
            values = list(pool.map(read, range(100)))
        result["report_1000_orders_8_clients"] = {
            **summary(values),
            "requests_per_second": round(100 / (perf_counter() - begin), 2),
            "errors": 0,
        }
    result["scope"] = (
        "Isolated PostgreSQL, real RabbitMQ/consumer processes, ASGI API with synthetic identity/provider; no production traffic or settlement"
    )
    result["acceptance_ms"] = dict(
        report_p95=2000, seat_contention_max=2500, confirmation_p95=2500
    )
    Path("/workspace/tmp/m10-performance.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps(result))
    assert result["report_1000_orders_8_clients"]["p95_ms"] <= 2000
    assert result["seat_contention"]["max_ms"] <= 2500
    assert result["provider_receipt_to_booking_ack"]["p95_ms"] <= 2500
