import os
from uuid import uuid4
import pytest
from sqlmodel import Session
from sqlalchemy import select
from cinema_platform.broker import Publisher, connect
from cinema_platform.events import EventEnvelope, OutboxRecord
from cinema_platform.outbox import relay_one
from review_service.events import ReviewFact
from review_service import service
from review_service.worker import process_one
from test_review_api import PREDICTOR


def test_review_events_reach_public_broker_with_separate_credential(review_store, review_settings):
    url = os.environ.get("TEST_AMQP_OPERATOR_PUBLIC", "")
    if "rabbitmq-test" not in url:
        pytest.skip("Dedicated test broker required")
    connection = connect(url)
    channel = connection.channel()
    queue = "review-test-" + uuid4().hex
    channel.queue_declare(queue, exclusive=True, auto_delete=True)
    for event_type in ["ReviewChanged.v1", "ReviewSentimentUpdated.v1"]:
        channel.queue_bind(queue, "cinema.events.v1", routing_key=event_type)
    publisher = Publisher(review_settings.amqp_public_url, "")
    try:
        review_settings.auto_approve = True
        with Session(review_store) as db:
            service.create_review(db, 1, 777, "Đánh giá chỉ trong DB test", review_settings)
        assert process_one(review_store, review_settings, PREDICTOR) == "succeeded"
        assert relay_one(review_store, publisher) and relay_one(review_store, publisher)
        assert not relay_one(review_store, publisher)
        received = []
        for _ in range(2):
            method, properties, body = channel.basic_get(queue, auto_ack=False)
            assert method is not None
            event = EventEnvelope.model_validate_json(body)
            ReviewFact.model_validate(event.data)
            assert "content" not in event.data and "user_id" not in event.data
            received.append(event)
            channel.basic_ack(method.delivery_tag)
        assert [e.aggregate_version for e in received] == [1, 2]
        assert {e.event_type for e in received} == {"ReviewChanged.v1", "ReviewSentimentUpdated.v1"}
        with Session(review_store) as db:
            assert {r.status for r in db.scalars(select(OutboxRecord))} == {"PUBLISHED"}
    finally:
        publisher.close()
        connection.close()
