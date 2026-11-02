from pathlib import Path
import sys

import pytest
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend/tests"))
from test_normalized_schema import pg, catalog, provider, provider_params  # noqa: E402,F401
from app.core.config import settings  # noqa: E402
from app.models import Booking, BookingDetail, Payment, Ticket  # noqa: E402
from app.repositories.payment_repo import PaymentRepository  # noqa: E402
from app.services.payment_service import PaymentService  # noqa: E402
from cinema_platform.events import OutboxRecord  # noqa: E402


@pytest.mark.parametrize("callback", ["return", "ipn"])
def test_confirmation_and_private_email_event_commit_once_together(pg, catalog, provider, monkeypatch, callback):
    monkeypatch.setattr(settings, "NOTIFICATION_TRANSPORT", "events")
    attempt = PaymentRepository.create_attempt(pg, catalog["booking"])
    params = provider_params(attempt)
    legacy = []
    monkeypatch.setattr("app.services.payment_service.send_payment_success_email_task.delay", lambda **kw: legacy.append(kw))
    for _ in range(2):
        if callback == "return":
            assert PaymentService.confirm_vnpay_payment(pg, catalog["booking"].id, "00", params)["status"] == "success"
        else:
            assert PaymentService.process_vnpay_ipn(pg, params)["RspCode"] in {"00", "02"}
    rows = pg.execute(select(OutboxRecord).where(OutboxRecord.aggregate_id == f"booking:{catalog['booking'].id}")).scalars().all()
    assert len(rows) == 2 and not legacy
    public = next(row for row in rows if row.destination == "public")
    private = next(row for row in rows if row.destination == "notification")
    assert not {"email", "to_email", "fullName", "phone", "ticket_code"} & public.payload["data"].keys()
    assert private.payload["data"]["to_email"] == catalog["user"].email
    assert isinstance(public.payload["data"]["total_amount"], str)


def test_failure_after_event_flush_rolls_back_ticket_and_outbox_but_preserves_provider_evidence(pg, catalog, provider, monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATION_TRANSPORT", "events")
    attempt = PaymentRepository.create_attempt(pg, catalog["booking"])
    params = provider_params(attempt)
    booking_id, payment_id = catalog["booking"].id, attempt.id
    pg.commit()  # Fixture data survives the application transaction rollback (outer test still rolls back).
    from app.services import integration_events
    original = integration_events.booking_confirmed
    def crash(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("Failure before confirmation commit")
    monkeypatch.setattr(integration_events, "booking_confirmed", crash)
    assert PaymentService.process_vnpay_ipn(pg, params)["RspCode"] == "99"
    assert pg.get(Booking, booking_id).booking_status == "PENDING"
    assert pg.get(Payment, payment_id).status == "PAID"
    assert pg.execute(select(Ticket).join(BookingDetail)
        .where(BookingDetail.booking_id == booking_id)).scalars().all() == []
    assert pg.execute(select(OutboxRecord).where(OutboxRecord.aggregate_id == f"booking:{booking_id}")).scalars().all() == []


def test_legacy_queued_task_bridges_to_one_private_outbox_instead_of_smtp(pg, catalog, provider, monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATION_TRANSPORT", "legacy")
    attempt = PaymentRepository.create_attempt(pg, catalog["booking"])
    assert PaymentService.process_vnpay_ipn(pg, provider_params(attempt))["RspCode"] == "00"
    monkeypatch.setattr(settings, "NOTIFICATION_TRANSPORT", "events")
    from app.worker import tasks
    from sqlmodel import Session
    monkeypatch.setattr(tasks, "engine", pg.bind)
    monkeypatch.setattr(tasks, "Session", lambda bind: Session(bind=bind, join_transaction_mode="create_savepoint"))
    monkeypatch.setattr(tasks, "send_payment_success_email", lambda **kwargs: pytest.fail("Legacy SMTP must be disabled after cutover"))
    for _ in range(2):
        result = tasks.send_payment_success_email_task.run(to_email="ignored-legacy@example.com", booking_detail={"bookingId": catalog["booking"].id})
        assert result["migrated"] and not result["sent"]
    rows = pg.execute(select(OutboxRecord).where(OutboxRecord.aggregate_id == f"booking:{catalog['booking'].id}")).scalars().all()
    assert len(rows) == 1 and rows[0].destination == "notification"
