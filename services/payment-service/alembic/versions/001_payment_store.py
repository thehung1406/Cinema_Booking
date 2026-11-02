from alembic import op
from cinema_platform import migrations_v1
revision="payment_001"
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.execute('\nCREATE TABLE payment_checkouts (\n\tbooking_id INTEGER NOT NULL, \n\tbooking_version INTEGER NOT NULL, \n\treservation_id VARCHAR(36) NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tamount NUMERIC(12, 2) NOT NULL, \n\tcurrency VARCHAR(3) NOT NULL, \n\tdeadline TIMESTAMP WITH TIME ZONE NOT NULL, \n\tdigest VARCHAR(64) NOT NULL, \n\tpayment_method VARCHAR(50) NOT NULL, \n\tbooking_date TIMESTAMP WITH TIME ZONE NOT NULL, \n\tprimary_payment_id INTEGER, \n\tPRIMARY KEY (booking_id, booking_version)\n)\n\n')
    op.execute("\nCREATE TABLE payments (\n\tid SERIAL NOT NULL, \n\tbooking_id INTEGER NOT NULL, \n\tprovider VARCHAR(30) NOT NULL, \n\tpayment_method VARCHAR(50) NOT NULL, \n\tmerchant_ref VARCHAR(100) NOT NULL, \n\ttransaction_ref VARCHAR(100), \n\tamount NUMERIC(12, 2) NOT NULL, \n\tcurrency VARCHAR(3) NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tpaid_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tcheckout_version INTEGER NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_payment_provider_transaction UNIQUE (provider, transaction_ref), \n\tCONSTRAINT ck_payment_amount_positive CHECK (amount>0), \n\tCONSTRAINT ck_payment_status CHECK (status IN ('PENDING','PAID','FAILED','CANCELLED')), \n\tFOREIGN KEY(booking_id, checkout_version) REFERENCES payment_checkouts (booking_id, booking_version), \n\tUNIQUE (merchant_ref)\n)\n\n")
    op.execute('\nCREATE TABLE payment_fulfillments (\n\tpayment_id INTEGER NOT NULL, \n\toutcome VARCHAR(20) NOT NULL, \n\treason VARCHAR(100) NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (payment_id), \n\tFOREIGN KEY(payment_id) REFERENCES payments (id)\n)\n\n')
    op.execute('\nCREATE TABLE payment_reconciliation (\n\tid VARCHAR(36) NOT NULL, \n\tpayment_id INTEGER NOT NULL, \n\treason VARCHAR(100) NOT NULL, \n\treference VARCHAR(150) NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tdetail JSON NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (payment_id, reason, reference), \n\tFOREIGN KEY(payment_id) REFERENCES payments (id)\n)\n\n')
    op.execute('\nCREATE TABLE provider_results (\n\tid VARCHAR(64) NOT NULL, \n\tpayment_id INTEGER NOT NULL, \n\tamount NUMERIC(14, 2) NOT NULL, \n\ttransaction_ref VARCHAR(100) NOT NULL, \n\tresponse_code VARCHAR(20) NOT NULL, \n\ttransaction_status VARCHAR(20) NOT NULL, \n\tsuccess BOOLEAN NOT NULL, \n\torigin VARCHAR(30) NOT NULL, \n\treceived_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(payment_id) REFERENCES payments (id)\n)\n\n')
    op.execute('CREATE INDEX ix_payment_checkouts_user_id ON payment_checkouts (user_id)')
    op.execute('CREATE INDEX ix_payments_booking_id ON payments (booking_id)')
    op.execute('CREATE INDEX ix_payment_reconciliation_payment_id ON payment_reconciliation (payment_id)')
    op.execute('CREATE INDEX ix_payment_reconciliation_status ON payment_reconciliation (status)')
    op.execute('CREATE INDEX ix_provider_results_payment_id ON provider_results (payment_id)')
    migrations_v1.create(op)
    op.execute("""
    CREATE FUNCTION payment_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Provider/checkout evidence is immutable'; END $$;
    CREATE TRIGGER provider_result_immutable BEFORE UPDATE OR DELETE ON provider_results FOR EACH ROW EXECUTE FUNCTION payment_immutable();
    CREATE FUNCTION payment_checkout_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='DELETE' OR (NEW.booking_id,NEW.booking_version,NEW.reservation_id,NEW.user_id,NEW.amount,NEW.currency,NEW.deadline,NEW.digest,NEW.payment_method,NEW.booking_date)
      IS DISTINCT FROM (OLD.booking_id,OLD.booking_version,OLD.reservation_id,OLD.user_id,OLD.amount,OLD.currency,OLD.deadline,OLD.digest,OLD.payment_method,OLD.booking_date)
      OR (OLD.primary_payment_id IS NOT NULL AND NEW.primary_payment_id IS DISTINCT FROM OLD.primary_payment_id) THEN RAISE EXCEPTION 'Checkout facts are immutable'; END IF; RETURN NEW;
    END $$;
    CREATE TRIGGER payment_checkout_immutable BEFORE UPDATE OR DELETE ON payment_checkouts FOR EACH ROW EXECUTE FUNCTION payment_checkout_immutable();
    CREATE FUNCTION payment_ledger_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF (NEW.booking_id,NEW.provider,NEW.payment_method,NEW.merchant_ref,NEW.amount,NEW.currency,NEW.checkout_version)
        IS DISTINCT FROM (OLD.booking_id,OLD.provider,OLD.payment_method,OLD.merchant_ref,OLD.amount,OLD.currency,OLD.checkout_version)
        OR (OLD.status='PAID' AND (NEW.status<>'PAID' OR NEW.transaction_ref IS DISTINCT FROM OLD.transaction_ref OR NEW.paid_at IS DISTINCT FROM OLD.paid_at)) THEN
        RAISE EXCEPTION 'Cannot rewrite payment financial facts or collected result'; END IF; RETURN NEW;
    END $$;
    CREATE TRIGGER payment_ledger BEFORE UPDATE ON payments FOR EACH ROW EXECUTE FUNCTION payment_ledger_guard();
    """)

def downgrade(): raise RuntimeError('Reconcile provider evidence before rollback')
