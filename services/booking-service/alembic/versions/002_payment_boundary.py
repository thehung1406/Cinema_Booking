from alembic import op
import sqlalchemy as sa
import json
revision="booking_002"
down_revision="booking_001"
branch_labels=None
depends_on=None

def upgrade():
    op.execute('\nCREATE TABLE booking_payment_receipts (\n\tpayment_id SERIAL NOT NULL, \n\tbooking_id INTEGER NOT NULL, \n\tbooking_version INTEGER NOT NULL, \n\tamount NUMERIC(14, 2) NOT NULL, \n\toutcome VARCHAR(20) NOT NULL, \n\treason VARCHAR(100) NOT NULL, \n\tresult JSON NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (payment_id)\n)\n\n')
    op.execute('\nCREATE TABLE payment_ownership (\n\tid SERIAL NOT NULL, \n\towner VARCHAR(20) NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n')
    op.execute('CREATE INDEX ix_booking_payment_receipts_booking_id ON booking_payment_receipts (booking_id)')
    op.execute("CREATE UNIQUE INDEX uq_booking_accepted_payment ON booking_payment_receipts (booking_id, booking_version) WHERE outcome='CONFIRMED'")
    op.execute("INSERT INTO payment_ownership(id,owner) VALUES (1,'legacy')")
    conn=op.get_bind()
    # Establish historical accepted-payment evidence while both tables are still
    # locally owned. Do not create capture events or resend customer mail.
    rows=conn.execute(sa.text("""SELECT p.id,p.booking_id,p.checkout_version,p.amount,b.total_amount,c.reservation_id,c.digest,b.booking_status,b.payment_status,
        (SELECT count(*) FROM tickets t JOIN booking_details d ON d.id=t.booking_detail_id WHERE d.booking_id=b.id AND t.status IN ('ISSUED','USED')) AS tickets,
        (SELECT count(*) FROM booking_details d WHERE d.booking_id=b.id) AS seats
        FROM payments p JOIN bookings b ON b.id=p.booking_id JOIN checkout_snapshots c ON c.booking_id=b.id
        WHERE p.status='PAID' ORDER BY p.id""")).mappings().all()
    accepted=set()
    for row in rows:
        valid=row['amount']==row['total_amount'] and row['booking_status']=='CONFIRMED' and row['payment_status']=='PAID' and row['tickets']==row['seats'] and row['seats']>0 and row['booking_id'] not in accepted
        outcome='CONFIRMED' if valid else 'REJECTED'; reason='TICKETS_ISSUED' if valid else 'LEGACY_RECONCILIATION_REQUIRED'
        if valid: accepted.add(row['booking_id'])
        result=dict(payment_id=row['id'],booking_id=row['booking_id'],booking_version=row['checkout_version'],reservation_id=row['reservation_id'],checkout_digest=row['digest'],outcome=outcome,reason=reason)
        conn.execute(sa.text("INSERT INTO booking_payment_receipts(payment_id,booking_id,booking_version,amount,outcome,reason,result,created_at) VALUES (:id,:booking_id,:checkout_version,:amount,:outcome,:reason,CAST(:result AS json),CURRENT_TIMESTAMP)"),{**row,'outcome':outcome,'reason':reason,'result':json.dumps(result)})
    op.execute("""
    CREATE FUNCTION legacy_payment_write_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE state text;
    BEGIN
      SELECT owner INTO state FROM payment_ownership WHERE id=1 FOR SHARE;
      IF state IS DISTINCT FROM 'legacy' THEN RAISE EXCEPTION 'Legacy Payment writer is frozen or transferred'; END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
    END $$;
    CREATE TRIGGER payment_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON payments FOR EACH ROW EXECUTE FUNCTION legacy_payment_write_guard();
    CREATE FUNCTION payment_receipt_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Booking payment receipt is immutable'; END $$;
    CREATE TRIGGER payment_receipt_immutable BEFORE UPDATE OR DELETE ON booking_payment_receipts FOR EACH ROW EXECUTE FUNCTION payment_receipt_immutable();
    """)

def downgrade(): raise RuntimeError('Payment ownership is terminal after transfer')
