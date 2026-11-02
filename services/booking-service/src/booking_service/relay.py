"""Dedicated relay process. No Redis lock, Celery email task or SMTP credential."""

import argparse
import logging
import time

from sqlalchemy.orm import Session

from .config import settings
from sqlalchemy import create_engine
engine=create_engine(settings.database_url,pool_pre_ping=True)
from cinema_platform.broker import Publisher
from cinema_platform.outbox import relay_one, replay

logger = logging.getLogger("cinema.outbox")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retry-event")
    parser.add_argument("--reason")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.retry_event:
        with Session(engine) as db, db.begin():
            replay(db, args.retry_event, "local-operator", args.reason or "")
        return
    if not settings.amqp_public_url or not settings.amqp_notification_url:
        raise RuntimeError("AMQP publisher destinations are not configured")
    if not settings.writes_enabled: raise RuntimeError("Booking relay is frozen")
    publisher = Publisher(settings.amqp_public_url, settings.amqp_notification_url)
    try:
        while True:
            try:
                if not relay_one(engine, publisher):
                    time.sleep(1)
            except Exception as exc:
                logger.error("relay_failed error_type=%s", type(exc).__name__)
                publisher.close()
                time.sleep(5)
    finally:
        publisher.close()


if __name__ == "__main__":
    main()
