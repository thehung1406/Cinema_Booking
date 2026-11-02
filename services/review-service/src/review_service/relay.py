import argparse
import logging
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from cinema_platform.broker import Publisher
from cinema_platform.outbox import relay_one, replay
from .config import Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retry-event")
    parser.add_argument("--reason")
    args = parser.parse_args()
    settings = Settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    if args.retry_event:
        with Session(engine) as db, db.begin():
            replay(db, args.retry_event, "local-operator", args.reason or "")
        return
    if not settings.amqp_public_url:
        raise RuntimeError("Review public publisher credential required")
    publisher = Publisher(settings.amqp_public_url, "")
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            if not settings.writes_enabled or not relay_one(engine, publisher):
                time.sleep(1)
        except Exception as exc:
            logging.getLogger("cinema.review.relay").error("relay_failed error_type=%s", type(exc).__name__)
            publisher.close()
            time.sleep(5)


if __name__ == "__main__":
    main()
