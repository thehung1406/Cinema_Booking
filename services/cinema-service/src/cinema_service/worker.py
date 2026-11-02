import time
import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from cinema_platform.logging import service_logger
from .config import Settings
from .models import Operation
from .clients import Clients
from .service import execute


def main():
    settings=Settings(); engine=create_engine(settings.database_url,pool_pre_ping=True)
    log=service_logger("cinema-worker")
    with httpx.Client(trust_env=False) as http:
        clients=Clients(settings,http)
        while True:
            try:
                if settings.writes_enabled:
                    with Session(engine) as db:
                        ids=list(db.scalars(select(Operation.id).where(Operation.status.in_(["PENDING","WAITING","RETRY"])).order_by(Operation.created_at).limit(50)))
                    for op_id in ids:
                        try: execute(engine,op_id,clients)
                        except Exception as exc: log.warning("operation processing deferred type=%s",type(exc).__name__)
            except Exception as exc: log.warning("worker store unavailable type=%s",type(exc).__name__)
            time.sleep(1)


if __name__=="__main__": main()
