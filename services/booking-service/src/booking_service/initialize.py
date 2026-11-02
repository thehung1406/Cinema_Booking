"""Final runtime initialization. Existing financial transfers require M9 cutover."""
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
from cinema_platform.events import ReplayAudit
from .config import Settings
from .models import Payment
from .models.payment_saga import PaymentOwnership

def initialize(engine):
    with Session(engine) as db,db.begin():
        row=db.scalar(select(PaymentOwnership).where(PaymentOwnership.id==1).with_for_update())
        if row.owner=='service':return
        if db.scalar(select(func.count()).select_from(Payment)):
            raise RuntimeError('Nonempty legacy financial store: complete the documented M9 handoff first')
        db.add(ReplayAudit(record_id='payment-fresh-runtime',actor='runtime-initializer',reason='Empty legacy payment ledger; initialize final Payment boundary'))
        row.owner='service'

def main():
    command.upgrade(Config('alembic.ini'),'head')
    initialize(create_engine(Settings().database_url))
if __name__=='__main__':main()
