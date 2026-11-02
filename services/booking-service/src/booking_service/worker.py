"""Dedicated expiry owner; per-show gate serializes with checkout/payment/check-in."""
import time
from sqlalchemy import create_engine,select
from sqlmodel import Session
from cinema_platform.logging import service_logger
from .config import Settings
from .models import Reservation
from .reservations import now,expire_show

def tick(engine):
    with Session(engine) as db:
        ids=list(db.scalars(select(Reservation.showtime_id).where(Reservation.status.in_(["ACTIVE","CHECKOUT"]),Reservation.expires_at<=now()).distinct().order_by(Reservation.showtime_id)))
    count=0
    for show_id in ids:
        with Session(engine) as db:
            count+=expire_show(db,show_id); db.commit()
    return count

def main():
    settings=Settings(); engine=create_engine(settings.database_url,pool_pre_ping=True)
    log=service_logger("booking-expiry")
    while True:
        try:
            if settings.writes_enabled: tick(engine)
        except Exception as exc: log.warning("expiry deferred type=%s",type(exc).__name__)
        time.sleep(1)

if __name__=="__main__": main()
