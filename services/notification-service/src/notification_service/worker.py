"""Two independently scalable processes: event consumer and SMTP dispatcher."""

import argparse
import logging
import time

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinema_platform.broker import EMAIL_QUEUE, connect
from cinema_platform.events import EventEnvelope
from .config import Settings
from .delivery import dispatch_one, receive
from .email import send

logger = logging.getLogger("cinema.notification")


def consume(engine, settings):
    connection = connect(settings.amqp_url)
    channel = connection.channel()
    channel.basic_qos(prefetch_count=10)

    def callback(ch, method, properties, body):
        try:
            if len(body) > 256_000:
                raise ValueError("Event too large")
            event = EventEnvelope.model_validate_json(body)
            with Session(engine) as db, db.begin():
                receive(db, event)
        except (ValueError, ValidationError):
            logger.warning("notification_event_rejected")
            ch.basic_reject(method.delivery_tag, requeue=False)
        except Exception:
            # Close/reconnect with backoff: broker requeues unacked messages on disconnect.
            raise
        else:
            ch.basic_ack(method.delivery_tag)

    channel.basic_consume(queue=EMAIL_QUEUE, on_message_callback=callback, auto_ack=False)
    try:
        channel.start_consuming()
    finally:
        if connection.is_open:
            connection.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["consume", "dispatch"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    while True:
        try:
            if args.mode == "consume":
                consume(engine, settings)
            elif not dispatch_one(engine, settings, send):
                time.sleep(1)
        except Exception as exc:
            logger.error("notification_worker_failed error_type=%s", type(exc).__name__)
            time.sleep(5)


if __name__ == "__main__":
    main()
