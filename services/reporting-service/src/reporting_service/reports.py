from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select
from .models import Projection, SourceState, now
from .config import SOURCES


def readiness(db):
    states = {r.source: r for r in db.scalars(select(SourceState))}
    return all(source in states and states[source].bootstrapped for source in SOURCES)


def report(db, filters, stale_seconds=60):
    if not readiness(db):
        raise HTTPException(503, "Đang nạp dữ liệu báo cáo")
    facts = {}
    for row in db.scalars(select(Projection)):
        if not row.deleted:
            facts.setdefault((row.source, row.kind), {})[row.key] = row.fact["payload"]
    configs = facts.get(("booking", "config"), {})
    gates = facts.get(("booking", "gate"), {})
    payments = facts.get(("payment", "payment"), {})
    films = facts.get(("catalog", "film"), {})

    def matches(c):
        return (
            c
            and filters.start_date
            <= date.fromisoformat(c["show_date"])
            <= filters.end_date
            and c["status"] != "CANCELLED"
            and (not filters.film_id or c["film_id"] == filters.film_id)
            and (not filters.theater_id or c["theater_id"] == filters.theater_id)
        )

    current = [
        configs.get(f"{g['showtime_id']}:{g['sales_version']}")
        for g in gates.values()
        if g["sales_version"] is not None
    ]
    slots = {
        (c["showtime_id"], sid)
        for c in current
        if matches(c)
        for sid in c["active_seat_ids"]
    }
    screened = {c["film_id"] for c in current if matches(c)}
    booked = {
        (r["showtime_id"], sid)
        for r in facts.get(("booking", "booked_seats"), {}).values()
        for sid in r["seat_ids"]
    }
    eligible = []
    for b in facts.get(("booking", "booking"), {}).values():
        c = configs.get(f"{b['showtime_id']}:{b['sales_version']}")
        p = payments.get(str(b.get("accepted_payment_id")))
        if (
            matches(c)
            and b["booking_status"] == "CONFIRMED"
            and b["payment_status"] == "PAID"
            and p
            and p["status"] == "PAID"
            and p["booking_id"] == b["id"]
            and p["checkout_version"] == b["accepted_checkout_version"]
            and p["currency"] == "VND"
            and Decimal(p["amount"]) == Decimal(b["total_amount"])
        ):
            eligible.append((b, c))
    sales = {}
    occupied = set()
    ticket_count = 0
    for b, c in eligible:
        label = films.get(str(c["film_id"]))
        if label is None:
            raise HTTPException(503, "Thiếu nhãn phim trong dữ liệu báo cáo")
        item = sales.setdefault(
            c["film_id"],
            dict(
                film_id=c["film_id"],
                title=label["title"],
                revenue=Decimal(0),
                bookings=0,
                tickets=0,
            ),
        )
        item["revenue"] += Decimal(b["total_amount"])
        item["bookings"] += 1
        for seat in b["seats"]:
            if seat["valid_ticket"]:
                ticket_count += 1
                item["tickets"] += 1
                occupied.add((b["showtime_id"], seat["seat_id"]))
    occupied &= slots & booked
    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    begin = datetime.combine(filters.start_date, time.min, tzinfo=tz)
    end = datetime.combine(filters.end_date + timedelta(days=1), time.min, tzinfo=tz)
    sentiments = dict(positive=0, neutral=0, negative=0, total=0)
    for r in facts.get(("review", "review"), {}).values():
        stamp = datetime.fromisoformat(r["updated_at"])
        if (
            r["is_deleted"]
            or r["moderation_status"] != "approved"
            or not begin <= stamp < end
            or stamp > now()
        ):
            continue
        if filters.theater_id and r["film_id"] not in screened:
            continue
        if (
            not filters.theater_id
            and filters.film_id
            and r["film_id"] != filters.film_id
        ):
            continue
        sentiments["total"] += 1
        if (
            r["sentiment_version"] == r["content_version"]
            and r["sentiment_status"] == "succeeded"
            and r["label"] in {"positive", "neutral", "negative"}
        ):
            sentiments[r["label"]] += 1
    analyzed = sum(sentiments[k] for k in ["positive", "neutral", "negative"])
    sentiments.update(
        pending=sentiments["total"] - analyzed,
        coverage=(
            round(100 * analyzed / sentiments["total"], 2) if sentiments["total"] else 0
        ),
    )
    states = list(db.scalars(select(SourceState).order_by(SourceState.source)))
    watermarks = {
        s.source: dict(
            snapshot_at=s.snapshot_at,
            checkpoint_at=s.checkpoint_at,
            verified_at=s.verified_at,
            observed_at=s.observed_at,
        )
        for s in states
    }
    stale = any(
        not s.verified_at or (now() - s.verified_at).total_seconds() > stale_seconds
        for s in states
    )
    return dict(
        revenue=sum((v["revenue"] for v in sales.values()), Decimal(0)),
        booking_count=len(eligible),
        ticket_count=ticket_count,
        seat_slots=len(slots),
        occupied_seats=len(occupied),
        occupancy=round(100 * len(occupied) / len(slots), 2) if slots else 0,
        by_film=[sales[k] for k in sorted(sales)],
        sentiments=sentiments,
        as_of=min((s.verified_at or s.snapshot_at for s in states)),
        filters=filters.model_dump(),
        watermarks=watermarks,
        stale=stale,
    )
