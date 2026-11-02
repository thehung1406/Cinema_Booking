from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from threading import Barrier
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cinema_platform.events import EventEnvelope, InboxRecord, utcnow
from notification_service.delivery import dispatch_one, receive, retry_job
from notification_service.email import build_message, send
from notification_service.main import create_app
from notification_service.models import DeliveryAttempt, DeliveryJob


def email_event():
    booking_id = uuid4().int % 1_000_000_000
    return EventEnvelope(
        event_type="BookingConfirmationEmailRequested.v1", producer="booking-monolith",
        aggregate_id=f"booking:{booking_id}", aggregate_version=1, correlation_id=str(uuid4()),
        data={"to_email": "migration@example.com", "booking_detail": {
            "bookingId": booking_id, "fullName": "Người kiểm thử", "filmTitle": "Phim kiểm thử",
            "theaterName": "Rạp test", "roomName": "P1", "showDate": "2026-11-02",
            "startTime": "20:00", "totalAmount": "185000.00", "seats": [{"seat_name": "A1"}],
            "foodItems": [{"quantity": 1, "name": "Combo test", "line_total": "110000.00"}],
        }},
    )


def insert_job(store, event):
    with Session(store) as db, db.begin():
        receive(db, event)


def test_inbox_and_job_rollback_together_and_deduplicate_after_ack_loss(store):
    event = email_event()
    with Session(store) as db:
        receive(db, event)
        db.rollback()
        assert db.scalar(select(func.count()).select_from(InboxRecord)) == 0
        assert db.scalar(select(func.count()).select_from(DeliveryJob)) == 0
    insert_job(store, event)
    with Session(store) as db, db.begin():
        assert receive(db, event) == "duplicate"
        assert db.scalar(select(func.count()).select_from(DeliveryJob)) == 1
        changed = event.model_copy(deep=True)
        changed.data["to_email"] = "different@example.com"
        with pytest.raises(ValueError):
            receive(db, changed)


def test_distinct_event_ids_cannot_create_two_jobs_for_same_confirmation(store):
    event = email_event()
    insert_job(store, event)
    duplicate = event.model_copy(update={"event_id": uuid4()})
    with Session(store) as db, db.begin():
        assert receive(db, duplicate) == "duplicate"
        assert db.scalar(select(func.count()).select_from(DeliveryJob)) == 1


def test_concurrent_consumers_create_one_job(store):
    event, barrier = email_event(), Barrier(2)
    def consume(_):
        barrier.wait(timeout=10)
        with Session(store) as db, db.begin():
            return receive(db, event)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(consume, range(2))) == ["accepted", "duplicate"]


def test_smtp_retry_dead_letter_and_audited_operator_retry(store, notification_settings):
    event = email_event()
    insert_job(store, event)
    def fail(data, settings):
        raise ConnectionError("do not store recipient or SMTP connection secret")
    for expected in ["RETRY", "DEAD"]:
        assert dispatch_one(store, notification_settings, fail)
        with Session(store) as db, db.begin():
            job = db.get(DeliveryJob, str(event.event_id))
            assert job.status == expected and job.last_error == "ConnectionError"
            job.next_attempt_at = utcnow()
    assert not dispatch_one(store, notification_settings, fail)
    with Session(store) as db, db.begin():
        retry_job(db, str(event.event_id), "admin:1", "SMTP configuration repaired")
    sent = []
    assert dispatch_one(store, notification_settings, lambda data, settings: sent.append(data))
    assert len(sent) == 1
    with Session(store) as db:
        assert db.get(DeliveryJob, str(event.event_id)).status == "SENT"
        assert db.scalar(select(func.count()).select_from(DeliveryAttempt)) == 4
        with pytest.raises(ValueError):
            retry_job(db, str(event.event_id), "admin:1", "cannot resend sent jobs")


def test_concurrent_dispatchers_do_not_send_same_job(store, notification_settings):
    insert_job(store, email_event())
    sent, barrier = [], Barrier(2)
    def worker(_):
        barrier.wait(timeout=10)
        return dispatch_one(store, notification_settings, lambda data, settings: sent.append(data))
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(worker, range(2))) == [False, True]
    assert len(sent) == 1


def test_crashed_dispatcher_lease_can_be_recovered(store, notification_settings):
    event = email_event()
    insert_job(store, event)
    with Session(store) as db, db.begin():
        job = db.get(DeliveryJob, str(event.event_id))
        job.status, job.lease_until, job.lease_token = "PROCESSING", utcnow() - timedelta(seconds=1), str(uuid4())
        job.attempts = 1
    assert dispatch_one(store, notification_settings, lambda data, settings: None)
    with Session(store) as db:
        assert db.get(DeliveryJob, str(event.event_id)).status == "SENT"


def test_delivery_api_needs_service_key_user_token_and_current_permission(store, notification_settings):
    event = email_event()
    insert_job(store, event)
    with Session(store) as db, db.begin():
        db.get(DeliveryJob, str(event.event_id)).status = "DEAD"
    principal = {"user_id": 1, "role": "ADMIN", "is_active": True, "permissions": ["notifications.manage"]}
    calls = []
    def identity(request):
        calls.append(request)
        return httpx.Response(200, json=principal)
    app = create_app(notification_settings, engine=store, transport=httpx.MockTransport(identity))
    path = f"/internal/v1/deliveries/{event.event_id}/retry"
    headers = {"X-Service-Key": notification_settings.service_key, "Authorization": "Bearer test-token"}
    with TestClient(app) as client:
        assert client.post(path, json={"reason": "repair"}).status_code == 401
        assert client.post(path, headers=headers, json={"reason": "repair"}).status_code == 200
        principal["permissions"] = []
        assert client.get("/internal/v1/deliveries/summary", headers=headers).status_code == 403
    assert len(calls) == 2


def test_actual_smtp_goes_to_local_capture_server_only(store, notification_settings):
    import os
    event = email_event()
    insert_job(store, event)
    assert notification_settings.smtp_host == "mailpit-test"
    assert dispatch_one(store, notification_settings, send)
    with httpx.Client(trust_env=False) as client:
        messages = client.get(os.environ["TEST_MAILPIT_URL"] + "/api/v1/messages").json()
    assert any(str(event.data["booking_detail"]["bookingId"]) in item["Subject"] for item in messages["messages"])
