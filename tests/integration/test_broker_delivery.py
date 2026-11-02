import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import pika
import httpx
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from cinema_platform.broker import DEAD_QUEUE, EMAIL_QUEUE, PRIVATE_EXCHANGE, Publisher, connect
from cinema_platform.events import EventEnvelope, MessagingBase
from cinema_platform.outbox import enqueue, relay_one
from notification_service.delivery import receive
from notification_service.models import DeliveryJob

# Reuse only the isolated test-store fixture, not any backend business model.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services/notification-service/tests"))
from notification_test_support import store  # noqa: E402,F401


@pytest.fixture
def broker():
    url = os.environ.get("TEST_AMQP_OPERATOR_PRIVATE", "")
    if "rabbitmq-test" not in url:
        pytest.skip("Isolated RabbitMQ test credentials required")
    connection = connect(url)
    channel = connection.channel()
    channel.queue_purge(EMAIL_QUEUE)
    channel.queue_purge(DEAD_QUEUE)
    try:
        yield channel
    finally:
        if connection.is_open:
            connection.close()


def example():
    booking_id = uuid4().int % 1_000_000_000
    return EventEnvelope(event_type="BookingConfirmationEmailRequested.v1", producer="test",
        aggregate_id=f"booking:{booking_id}", aggregate_version=1, correlation_id=str(uuid4()),
        data={"to_email": "broker-test@example.com", "booking_detail": {
            "bookingId": booking_id, "totalAmount": "75000.00", "seats": [{"seat_name": "A1"}],
        }})


def test_real_broker_confirm_ack_loss_redelivery_creates_one_delivery_job(store, broker):
    event = example()
    publisher = Publisher(os.environ["AMQP_PUBLIC_URL"], os.environ["AMQP_NOTIFICATION_URL"])
    try:
        publisher("notification", event)
    finally:
        publisher.close()
    method, props, body = broker.basic_get(EMAIL_QUEUE, auto_ack=False)
    assert method and props.message_id == str(event.event_id)
    with Session(store) as db, db.begin():
        assert receive(db, EventEnvelope.model_validate_json(body)) == "accepted"
    broker.basic_nack(method.delivery_tag, requeue=True)  # Commit happened, ACK was lost.
    method, props, body = broker.basic_get(EMAIL_QUEUE, auto_ack=False)
    assert method and method.redelivered
    with Session(store) as db, db.begin():
        assert receive(db, EventEnvelope.model_validate_json(body)) == "duplicate"
        assert db.scalar(select(func.count()).select_from(DeliveryJob)) == 1
    broker.basic_ack(method.delivery_tag)


def test_notification_credential_cannot_enter_public_vhost_or_publish(broker):
    url = os.environ["NOTIFICATION_AMQP_URL"]
    with pytest.raises(pika.exceptions.AMQPConnectionError):
        connect(url.replace("%2Fcinema-private", "%2Fcinema-public"))
    connection = connect(url)
    try:
        channel = connection.channel()
        channel.confirm_delivery()
        with pytest.raises(pika.exceptions.ChannelClosedByBroker):
            channel.basic_publish(PRIVATE_EXCHANGE, "BookingConfirmationEmailRequested.v1", b"not authorized", mandatory=True)
    finally:
        if connection.is_open:
            connection.close()


def test_running_consumer_rejects_poison_event_to_dead_letter_queue(broker):
    worker = subprocess.Popen([sys.executable, "-m", "notification_service.worker", "consume"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        broker.basic_publish(PRIVATE_EXCHANGE, "BookingConfirmationEmailRequested.v1", b"invalid-json")
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            method, _, body = broker.basic_get(DEAD_QUEUE, auto_ack=True)
            if method:
                assert body == b"invalid-json"
                break
            time.sleep(0.1)
        else:
            pytest.fail("Poison event was not dead-lettered by the real consumer")
    finally:
        worker.terminate()
        worker.wait(timeout=10)


def test_separate_source_db_outbox_to_running_consumer_dispatcher_and_smtp(broker):
    event = example()
    source_root = create_engine(os.environ["TEST_POSTGRES_URL"])
    schema = "pipeline_test_" + uuid4().hex
    with source_root.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    source = create_engine(os.environ["TEST_POSTGRES_URL"], connect_args={"options": f"-csearch_path={schema}"})
    destination = create_engine(os.environ["NOTIFICATION_DATABASE_URL"])
    publisher = Publisher(os.environ["AMQP_PUBLIC_URL"], os.environ["AMQP_NOTIFICATION_URL"])
    workers = []
    try:
        MessagingBase.metadata.create_all(source)
        with Session(source) as db, db.begin():
            enqueue(db, event, "notification")
        for mode in ("consume", "dispatch"):
            workers.append(subprocess.Popen([sys.executable, "-m", "notification_service.worker", mode], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        assert relay_one(source, publisher)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            with Session(destination) as db:
                job = db.get(DeliveryJob, str(event.event_id))
                if job and job.status == "SENT":
                    break
            time.sleep(0.1)
        else:
            pytest.fail("Outbox event did not reach SMTP through both running service processes")
        publisher("notification", event)  # A late producer replay cannot resend the SENT job.
        time.sleep(0.3)
        with Session(destination) as db:
            assert db.scalar(select(func.count()).select_from(DeliveryJob).where(DeliveryJob.id == str(event.event_id))) == 1
        with httpx.Client(trust_env=False) as http:
            messages = http.get(os.environ["TEST_MAILPIT_URL"] + "/api/v1/messages").json()["messages"]
        assert len([item for item in messages if str(event.data["booking_detail"]["bookingId"]) in item["Subject"]]) == 1
    finally:
        for worker in workers:
            worker.terminate()
            worker.wait(timeout=10)
        publisher.close()
        source.dispose()
        destination.dispose()
        with source_root.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        source_root.dispose()
