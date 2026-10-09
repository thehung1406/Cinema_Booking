from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from sqlmodel import Session, select
from app.models import Payment


class PaymentRepository:
    @staticmethod
    def get_by_ref(db: Session, merchant_ref: str, for_update: bool = False):
        statement = select(Payment).where(Payment.merchant_ref == merchant_ref)
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return db.exec(statement).first()

    @staticmethod
    def create_attempt(db: Session, booking):
        payment = Payment(booking_id=booking.id, provider="VNPAY", payment_method="VNPAY",
                          merchant_ref=uuid4().hex, amount=Decimal(str(booking.total_amount)))
        db.add(payment)
        db.flush()
        return payment

    @staticmethod
    def record_result(db: Session, payment: Payment, params: dict, success: bool):
        # A late failed response cannot downgrade a previously paid transaction.
        if payment.status == "PAID":
            return
        transaction_ref = params.get("vnp_TransactionNo")
        payment.transaction_ref = str(transaction_ref) if transaction_ref and str(transaction_ref) != "0" else None
        payment.status = "PAID" if success else "FAILED"
        payment.updated_at = datetime.now(timezone.utc)
        if success:
            payment.paid_at = payment.updated_at
        db.add(payment)
        db.flush()
