from pathlib import Path
from decimal import Decimal
from alembic import command
from alembic.config import Config
from sqlalchemy import text,select,func
from sqlmodel import Session
import pytest
from booking_service import reservations,bookings
from booking_service.models import Booking,Payment as OldPayment
from booking_service.payment_repo import PaymentRepository
from booking_service.payments import PaymentService
from booking_service.models.payment_saga import PaymentReceipt
from test_booking import request,params
from payment_service.models import Payment,Checkout,Fulfillment,ProviderResult
from payment_service.migrate import transfer


def test_real_legacy_boundary_upgrade_and_payment_copy_preserve_all_original_facts(ready,payment_store):
    with Session(ready) as db:
        rid=reservations.hold(db,1,[1,2],1)[0]['reservation_id']
        bid=bookings.create(db,request(reservation=rid),1,'copy-legacy')['bookingId']
        payment=PaymentRepository.create_attempt(db,db.get(Booking,bid)); body=params(payment); db.commit()
        assert PaymentService.confirm_vnpay_payment(db,bid,'00',body)['status']=='success'
    # Recreate the exact pre-boundary state, then run the actual new migration
    # against issued historical tickets rather than manually inventing receipts.
    with ready.begin() as conn:
        conn.execute(text('DROP FUNCTION legacy_payment_write_guard() CASCADE; DROP FUNCTION payment_receipt_immutable() CASCADE; DROP TABLE booking_payment_receipts; DROP TABLE payment_ownership;'))
        conn.execute(text("UPDATE alembic_version SET version_num='booking_001'"))
    command.upgrade(Config(str(Path(__file__).resolve().parents[2]/'booking-service/alembic.ini')),'head')
    with Session(ready) as db: assert db.get(PaymentReceipt,1).outcome=='CONFIRMED'
    with pytest.raises(ValueError): transfer(ready,payment_store,apply=True,frozen=False)
    with pytest.raises(ValueError): transfer(ready,payment_store,apply=True,frozen=True)
    with ready.begin() as conn:
        conn.execute(text("UPDATE payment_ownership SET owner='maintenance'"))
        conn.execute(text("SELECT setval(pg_get_serial_sequence('payments','id'),3000000,true)"))
    result=transfer(ready,payment_store,apply=True,frozen=True)
    assert result['verified'] and result['copied'] and result['payments']==1
    assert transfer(ready,payment_store)['payment_sha256']==result['payment_sha256']
    assert not transfer(ready,payment_store,apply=True,frozen=True)['copied']
    with Session(payment_store) as db:
        old=db.get(Payment,1)
        assert old.status=='PAID' and old.transaction_ref==body['vnp_TransactionNo'] and old.merchant_ref==body['vnp_TxnRef'] and old.amount==Decimal('150000.00')
        assert db.get(Fulfillment,1).outcome=='CONFIRMED'
        assert db.scalar(select(ProviderResult)).origin=='LEGACY_TRANSFER'
        assert db.get(Checkout,(bid,1)).primary_payment_id==1
        assert db.execute(text("SELECT nextval(pg_get_serial_sequence('payments','id'))")).scalar_one()>3000000
    with payment_store.begin() as conn: conn.execute(text("UPDATE payments SET updated_at=updated_at+interval '1 second'"))
    with pytest.raises(ValueError): transfer(ready,payment_store,apply=True,frozen=True)
