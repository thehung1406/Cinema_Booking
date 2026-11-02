"""Booking is the only process that commits seats, booking and tickets."""
import time
from sqlalchemy import create_engine
from cinema_platform.consume import consume_queue
from cinema_platform.logging import service_logger
from .config import Settings
from .payment_saga import receive


def main():
    settings=Settings(); engine=create_engine(settings.database_url,pool_pre_ping=True)
    log=service_logger('booking-payment')
    if not settings.writes_enabled: raise RuntimeError('Booking consumer is frozen')
    while True:
        try: consume_queue(engine,settings.amqp_payment_consumer_url,'booking.payment.v1',receive)
        except Exception as exc: log.warning('capture deferred type=%s',type(exc).__name__); time.sleep(5)

if __name__=='__main__': main()
