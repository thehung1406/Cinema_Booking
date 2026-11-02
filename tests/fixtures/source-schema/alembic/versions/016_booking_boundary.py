"""Freeze the legacy Booking/payment store, projections and messaging after M8."""
from alembic import op
revision="016"
down_revision="015"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("INSERT INTO domain_ownership(domain,owner,updated_at) VALUES ('booking','monolith',CURRENT_TIMESTAMP)")
    op.execute("""CREATE FUNCTION booking_legacy_write_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE state text;
    BEGIN
      SELECT owner INTO state FROM domain_ownership WHERE domain='booking' FOR SHARE;
      IF state IS DISTINCT FROM 'monolith' THEN RAISE EXCEPTION 'Legacy Booking/payment writer is frozen or transferred'; END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
    END $$;""")
    for table in ("bookings","booking_details","booking_food_items","payments","tickets","seat_status","booking_sales_configurations","booking_sales_gates","outbox_events","inbox_events","message_replay_audits"):
        op.execute(f"CREATE TRIGGER booking_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION booking_legacy_write_guard()")

def downgrade():
    raise RuntimeError("Reconcile Booking, reservations, checkout/payment and outbox before downgrade")
