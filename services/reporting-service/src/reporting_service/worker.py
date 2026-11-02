import time
from sqlalchemy import create_engine
from cinema_platform.consume import consume_queue
from cinema_platform.logging import service_logger
from .config import Settings
from .projection import receive


def main():
    cfg = Settings()
    engine = create_engine(cfg.database_url, pool_pre_ping=True)
    log = service_logger("reporting-consumer")
    if not cfg.writes_enabled:
        raise RuntimeError("Reporting consumer is frozen")
    while True:
        try:
            consume_queue(engine, cfg.amqp_url, "reporting.bootstrap.v1", receive)
        except Exception as exc:
            log.warning("consumer deferred type=%s", type(exc).__name__)
            time.sleep(3)


if __name__ == "__main__":
    main()
