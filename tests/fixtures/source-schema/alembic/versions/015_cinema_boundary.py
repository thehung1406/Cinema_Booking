"""Cinema ownership and Booking-owned versioned sales configurations."""
from alembic import op
import sqlalchemy as sa

revision="015"
down_revision="014"
branch_labels=None
depends_on=None


def upgrade():
    op.execute("INSERT INTO domain_ownership(domain,owner,updated_at) VALUES ('cinema','monolith',CURRENT_TIMESTAMP)")
    op.execute('\nCREATE TABLE booking_sales_configurations (\n\tshowtime_id INTEGER NOT NULL, \n\tsales_version INTEGER NOT NULL, \n\tdigest VARCHAR(64) NOT NULL, \n\tfilm_id INTEGER NOT NULL, \n\troom_id INTEGER NOT NULL, \n\ttheater_id INTEGER NOT NULL, \n\tshow_date DATE NOT NULL, \n\tstart_time TIME WITHOUT TIME ZONE NOT NULL, \n\tend_time TIME WITHOUT TIME ZONE NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tsnapshot JSONB NOT NULL, \n\timported_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (showtime_id, sales_version)\n)\n\n')
    op.execute('CREATE INDEX ix_booking_sales_configurations_film_id ON booking_sales_configurations (film_id)')
    op.execute('CREATE INDEX ix_booking_sales_configurations_room_id ON booking_sales_configurations (room_id)')
    op.execute('CREATE INDEX ix_booking_sales_configurations_theater_id ON booking_sales_configurations (theater_id)')
    op.execute('\nCREATE TABLE booking_sales_gates (\n\tshowtime_id INTEGER NOT NULL, \n\tsales_version INTEGER, \n\tepoch INTEGER NOT NULL, \n\taction VARCHAR(20) NOT NULL, \n\tis_open BOOLEAN NOT NULL, \n\tPRIMARY KEY (showtime_id), \n\tFOREIGN KEY(showtime_id, sales_version) REFERENCES booking_sales_configurations (showtime_id, sales_version) ON DELETE RESTRICT\n)\n\n')

    for table in ("bookings", "seat_status"):
        op.add_column(table, sa.Column("sales_version", sa.Integer()))
        op.execute(f"UPDATE {table} SET sales_version=1")
    inspector=sa.inspect(op.get_bind())
    for table in ("bookings", "booking_details", "seat_status"):
        for fk in inspector.get_foreign_keys(table):
            if fk["referred_table"] in {"showtimes", "seats"}:
                op.drop_constraint(fk["name"], table, type_="foreignkey")
    install_guards()


def install_guards():
    op.execute("""
    CREATE FUNCTION cinema_legacy_write_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE state text;
    BEGIN
      SELECT owner INTO state FROM domain_ownership WHERE domain='cinema' FOR SHARE;
      IF state IS DISTINCT FROM 'monolith' THEN RAISE EXCEPTION 'Cinema legacy writer is frozen or transferred'; END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
    END $$;
    CREATE FUNCTION booking_sales_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Published sales configuration is immutable'; END $$;
    CREATE TRIGGER immutable_sales_configuration BEFORE UPDATE OR DELETE ON booking_sales_configurations
      FOR EACH ROW EXECUTE FUNCTION booking_sales_immutable();

    CREATE OR REPLACE FUNCTION cinema_validate_booking_seat() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE target_show integer; target_version integer; buyer integer; state text; payload jsonb;
            gate_version integer; gate_open boolean; seat jsonb;
    BEGIN
      SELECT owner INTO state FROM domain_ownership WHERE domain='cinema';
      IF TG_TABLE_NAME='booking_details' THEN
        SELECT showtime_id,sales_version,user_id INTO target_show,target_version,buyer FROM bookings WHERE id=NEW.booking_id;
      ELSE target_show:=NEW.showtime_id; target_version:=NEW.sales_version; END IF;
      IF TG_TABLE_NAME='seat_status' THEN
        IF state='maintenance' AND NEW.status='HOLD' THEN
          RAISE EXCEPTION 'Cinema is frozen; no new or extended holds' USING ERRCODE='23514';
        END IF;
      END IF;
      IF state IS DISTINCT FROM 'service' THEN
        IF NOT EXISTS (SELECT 1 FROM seats s JOIN showtimes sh ON sh.room_id=s.room_id
                       WHERE s.id=NEW.seat_id AND sh.id=target_show) THEN
          RAISE EXCEPTION 'Seat belongs to another showtime room' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END IF;
      SELECT sales_version,is_open INTO gate_version,gate_open FROM booking_sales_gates WHERE showtime_id=target_show FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'No acknowledged sales configuration' USING ERRCODE='23514'; END IF;
      SELECT snapshot INTO payload FROM booking_sales_configurations WHERE showtime_id=target_show AND sales_version=target_version;
      IF payload IS NULL THEN RAISE EXCEPTION 'Unknown sales version' USING ERRCODE='23514'; END IF;
      SELECT value INTO seat FROM jsonb_array_elements(payload->'seats') WHERE (value->>'id')::integer=NEW.seat_id;
      IF seat IS NULL THEN RAISE EXCEPTION 'Seat is not in published configuration' USING ERRCODE='23514'; END IF;
      IF TG_TABLE_NAME='seat_status' THEN
        IF TG_OP='UPDATE' AND OLD.status='BOOKED' AND
           (NEW.seat_id,NEW.showtime_id,NEW.sales_version,NEW.status) IS DISTINCT FROM (OLD.seat_id,OLD.showtime_id,OLD.sales_version,OLD.status) THEN
          RAISE EXCEPTION 'Booked sales reference is immutable' USING ERRCODE='23514';
        END IF;
        IF NEW.status='HOLD' AND (NOT gate_open OR target_version<>gate_version OR seat->>'status'<>'ACTIVE'
          OR NEW.hold_by_user_id IS NULL OR NEW.hold_expired_at IS NULL OR NEW.hold_expired_at<=CURRENT_TIMESTAMP
          OR payload->>'status'<>'ACTIVE' OR payload->'room'->>'status'<>'ACTIVE'
          OR ((payload->>'show_date')::date+(payload->>'start_time')::time)<=CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh') THEN
          RAISE EXCEPTION 'New holds are closed or have a stale sales version' USING ERRCODE='23514';
        END IF;
        IF NEW.status='BOOKED' AND (TG_OP='INSERT' OR OLD.status<>'BOOKED') THEN
          IF TG_OP='INSERT' OR OLD.status<>'HOLD' OR OLD.hold_expired_at<=CURRENT_TIMESTAMP
             OR OLD.sales_version IS DISTINCT FROM NEW.sales_version OR target_version<>gate_version THEN
            RAISE EXCEPTION 'Cannot book an expired or stale hold' USING ERRCODE='23514';
          END IF;
        END IF;
      ELSE
        IF TG_OP='INSERT' AND (NEW.price<>(seat->>'price')::numeric OR NOT EXISTS (
          SELECT 1 FROM seat_status ss WHERE ss.showtime_id=target_show AND ss.seat_id=NEW.seat_id
          AND ss.sales_version=target_version AND ss.status='HOLD' AND ss.hold_by_user_id=buyer AND ss.hold_expired_at>CURRENT_TIMESTAMP)) THEN
          RAISE EXCEPTION 'Booking detail requires published price and active owned hold' USING ERRCODE='23514';
        END IF;
        IF TG_OP='UPDATE' AND (NEW.price,NEW.seat_id,NEW.booking_id) IS DISTINCT FROM (OLD.price,OLD.seat_id,OLD.booking_id) THEN
          RAISE EXCEPTION 'Booking seat snapshot cannot change' USING ERRCODE='23514';
        END IF;
      END IF;
      RETURN NEW;
    END $$;

    CREATE FUNCTION booking_sales_version_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE state text; current_version integer;
    BEGIN
      SELECT owner INTO state FROM domain_ownership WHERE domain='cinema';
      IF state='maintenance' AND TG_OP='INSERT' THEN RAISE EXCEPTION 'Cinema migration has frozen new bookings' USING ERRCODE='23514'; END IF;
      IF state='service' THEN
        SELECT sales_version INTO current_version FROM booking_sales_gates WHERE showtime_id=NEW.showtime_id FOR UPDATE;
        IF NOT FOUND OR NOT EXISTS (SELECT 1 FROM booking_sales_configurations WHERE showtime_id=NEW.showtime_id AND sales_version=NEW.sales_version) THEN
          RAISE EXCEPTION 'Booking needs an acknowledged sales version' USING ERRCODE='23514';
        END IF;
        IF TG_OP='INSERT' AND (NEW.sales_version<>current_version OR NOT EXISTS (
          SELECT 1 FROM seat_status WHERE showtime_id=NEW.showtime_id AND sales_version=NEW.sales_version
          AND hold_by_user_id=NEW.user_id AND status='HOLD' AND hold_expired_at>CURRENT_TIMESTAMP)) THEN
          RAISE EXCEPTION 'Booking needs a current owned hold' USING ERRCODE='23514';
        END IF;
        IF TG_OP='UPDATE' AND (NEW.showtime_id,NEW.sales_version) IS DISTINCT FROM (OLD.showtime_id,OLD.sales_version) THEN
          RAISE EXCEPTION 'Booking sales reference is immutable' USING ERRCODE='23514';
        END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER booking_sales_version BEFORE INSERT OR UPDATE ON bookings FOR EACH ROW EXECUTE FUNCTION booking_sales_version_guard();
    CREATE OR REPLACE FUNCTION cinema_validate_ticket() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE b_id integer; s_id integer; buyer integer; ver integer; seat integer; state text;
    BEGIN
      SELECT b.id,b.showtime_id,b.user_id,b.sales_version,d.seat_id INTO b_id,s_id,buyer,ver,seat
      FROM booking_details d JOIN bookings b ON b.id=d.booking_id
      WHERE d.id=NEW.booking_detail_id AND b.payment_status='PAID' AND b.booking_status='CONFIRMED';
      IF NOT FOUND THEN RAISE EXCEPTION 'Ticket requires a paid, confirmed booking' USING ERRCODE='23514'; END IF;
      SELECT owner INTO state FROM domain_ownership WHERE domain='cinema';
      IF state='service' THEN
        PERFORM 1 FROM booking_sales_gates WHERE showtime_id=s_id FOR UPDATE;
        IF NOT EXISTS (SELECT 1 FROM seat_status WHERE showtime_id=s_id AND seat_id=seat AND status='BOOKED' AND sales_version=ver) THEN
          RAISE EXCEPTION 'Ticket requires the booked sales version' USING ERRCODE='23514';
        END IF;
        IF NEW.status IN ('ISSUED','USED') AND EXISTS (
          SELECT 1 FROM tickets t JOIN booking_details d ON d.id=t.booking_detail_id JOIN bookings b ON b.id=d.booking_id
          WHERE b.showtime_id=s_id AND d.seat_id=seat AND t.status IN ('ISSUED','USED') AND t.id IS DISTINCT FROM NEW.id) THEN
          RAISE EXCEPTION 'Seat already has an active ticket' USING ERRCODE='23514';
        END IF;
      END IF;
      RETURN NEW;
    END $$;

    """)
    for table in ("theaters", "cinema_rooms", "seats", "seat_types", "showtimes"):
        op.execute(f"CREATE TRIGGER cinema_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION cinema_legacy_write_guard()")


def downgrade():
    raise RuntimeError("Cinema boundary requires explicit data/configuration reconciliation; do not drop sales history")
