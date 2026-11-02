"""Booking with co-located legacy payment, immutable checkout and reservation fences."""
from alembic import op
from cinema_platform import migrations_v1
revision="booking_001"
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.execute("\nCREATE TABLE reservations (\n\tid VARCHAR(36) NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tshowtime_id INTEGER NOT NULL, \n\tsales_version INTEGER NOT NULL, \n\tseat_ids JSON NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_reservation_status CHECK (status IN ('ACTIVE','CHECKOUT','CONFIRMED','EXPIRED','RELEASED'))\n)\n\n")
    op.execute("\nCREATE TABLE bookings (\n\tid SERIAL NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tcustomer_full_name VARCHAR(100), \n\tcustomer_email VARCHAR(100), \n\tcustomer_phone VARCHAR(15), \n\tcatalog_film_snapshot JSON DEFAULT '{}' NOT NULL, \n\tsales_version INTEGER, \n\tfood_quote_id VARCHAR(36), \n\tfood_quote_version INTEGER, \n\tfood_quote_expires_at TIMESTAMP WITH TIME ZONE, \n\tshowtime_id INTEGER NOT NULL, \n\tbooking_date TIMESTAMP WITH TIME ZONE NOT NULL, \n\ttotal_amount NUMERIC(12, 2) NOT NULL, \n\tpayment_method VARCHAR(50), \n\tpayment_status VARCHAR(20) DEFAULT 'PENDING' NOT NULL, \n\tbooking_status VARCHAR(20) DEFAULT 'PENDING' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE, \n\treservation_id VARCHAR(36), \n\tbooking_version INTEGER NOT NULL, \n\tcurrency VARCHAR(3) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_booking_total_positive CHECK (total_amount > 0), \n\tUNIQUE (reservation_id), \n\tFOREIGN KEY(reservation_id) REFERENCES reservations (id)\n)\n\n")
    op.execute("\nCREATE TABLE seat_status (\n\tid SERIAL NOT NULL, \n\tseat_id INTEGER NOT NULL, \n\tshowtime_id INTEGER NOT NULL, \n\tstatus VARCHAR(20) DEFAULT 'AVAILABLE' NOT NULL, \n\tversion INTEGER DEFAULT '0' NOT NULL, \n\thold_by_user_id INTEGER, \n\thold_expired_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tsales_version INTEGER, \n\treservation_id VARCHAR(36), \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_seat_showtime UNIQUE (showtime_id, seat_id), \n\tFOREIGN KEY(reservation_id) REFERENCES reservations (id)\n)\n\n")
    op.execute('\nCREATE TABLE booking_details (\n\tid SERIAL NOT NULL, \n\tbooking_id INTEGER NOT NULL, \n\tseat_id INTEGER NOT NULL, \n\tprice NUMERIC(12, 2) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_booking_detail_seat UNIQUE (booking_id, seat_id), \n\tCONSTRAINT ck_booking_detail_price CHECK (price >= 0), \n\tFOREIGN KEY(booking_id) REFERENCES bookings (id) ON DELETE RESTRICT\n)\n\n')
    op.execute('\nCREATE TABLE booking_food_items (\n\tid SERIAL NOT NULL, \n\tbooking_id INTEGER NOT NULL, \n\tfood_item_id INTEGER NOT NULL, \n\tname VARCHAR(150) NOT NULL, \n\tcategory VARCHAR(20) NOT NULL, \n\tquantity INTEGER NOT NULL, \n\tunit_price NUMERIC(12, 2) NOT NULL, \n\tcomponents JSON NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_booking_food UNIQUE (booking_id, food_item_id), \n\tCONSTRAINT ck_booking_food_quantity CHECK (quantity BETWEEN 1 AND 20), \n\tCONSTRAINT ck_booking_food_price CHECK (unit_price > 0), \n\tFOREIGN KEY(booking_id) REFERENCES bookings (id) ON DELETE RESTRICT\n)\n\n')
    op.execute('\nCREATE TABLE booking_idempotency (\n\tuser_id INTEGER NOT NULL, \n\tkey VARCHAR(128) NOT NULL, \n\trequest_hash VARCHAR(64) NOT NULL, \n\tbooking_id INTEGER NOT NULL, \n\tresponse JSON NOT NULL, \n\tPRIMARY KEY (user_id, key), \n\tFOREIGN KEY(booking_id) REFERENCES bookings (id) ON DELETE RESTRICT\n)\n\n')
    op.execute('\nCREATE TABLE checkout_snapshots (\n\tbooking_id INTEGER NOT NULL, \n\tbooking_version INTEGER NOT NULL, \n\treservation_id VARCHAR(36) NOT NULL, \n\tamount NUMERIC(12, 2) NOT NULL, \n\tcurrency VARCHAR(3) NOT NULL, \n\tdeadline TIMESTAMP WITH TIME ZONE NOT NULL, \n\tdigest VARCHAR(64) NOT NULL, \n\tsnapshot JSON NOT NULL, \n\tPRIMARY KEY (booking_id), \n\tFOREIGN KEY(booking_id) REFERENCES bookings (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(reservation_id) REFERENCES reservations (id)\n)\n\n')
    op.execute("\nCREATE TABLE payments (\n\tid SERIAL NOT NULL, \n\tbooking_id INTEGER NOT NULL, \n\tprovider VARCHAR(30) NOT NULL, \n\tpayment_method VARCHAR(50) NOT NULL, \n\tmerchant_ref VARCHAR(100) NOT NULL, \n\ttransaction_ref VARCHAR(100), \n\tamount NUMERIC(12, 2) NOT NULL, \n\tcurrency VARCHAR(3) NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tpaid_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tcheckout_version INTEGER NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_payment_provider_transaction UNIQUE (provider, transaction_ref), \n\tCONSTRAINT ck_payment_amount_positive CHECK (amount > 0), \n\tCONSTRAINT ck_payment_status CHECK (status IN ('PENDING','PAID','FAILED','CANCELLED')), \n\tFOREIGN KEY(booking_id) REFERENCES bookings (id) ON DELETE RESTRICT, \n\tUNIQUE (merchant_ref)\n)\n\n")
    op.execute("\nCREATE TABLE tickets (\n\tid SERIAL NOT NULL, \n\tbooking_detail_id INTEGER NOT NULL, \n\tticket_code VARCHAR(100) NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tissued_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tused_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_ticket_status CHECK (status IN ('ISSUED','USED','CANCELLED')), \n\tUNIQUE (booking_detail_id), \n\tFOREIGN KEY(booking_detail_id) REFERENCES booking_details (id) ON DELETE RESTRICT, \n\tUNIQUE (ticket_code)\n)\n\n")
    op.execute('\nCREATE TABLE booking_sales_configurations (\n\tshowtime_id INTEGER NOT NULL, \n\tsales_version INTEGER NOT NULL, \n\tdigest VARCHAR(64) NOT NULL, \n\tfilm_id INTEGER NOT NULL, \n\troom_id INTEGER NOT NULL, \n\ttheater_id INTEGER NOT NULL, \n\tshow_date DATE NOT NULL, \n\tstart_time TIME WITHOUT TIME ZONE NOT NULL, \n\tend_time TIME WITHOUT TIME ZONE NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tsnapshot JSONB NOT NULL, \n\timported_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (showtime_id, sales_version)\n)\n\n')
    op.execute('\nCREATE TABLE booking_sales_gates (\n\tshowtime_id INTEGER NOT NULL, \n\tsales_version INTEGER, \n\tepoch INTEGER NOT NULL, \n\taction VARCHAR(20) NOT NULL, \n\tis_open BOOLEAN NOT NULL, \n\tPRIMARY KEY (showtime_id), \n\tFOREIGN KEY(showtime_id, sales_version) REFERENCES booking_sales_configurations (showtime_id, sales_version) ON DELETE RESTRICT\n)\n\n')
    op.execute('CREATE INDEX ix_reservations_showtime_id ON reservations (showtime_id)')
    op.execute('CREATE INDEX ix_reservations_user_id ON reservations (user_id)')
    op.execute("CREATE UNIQUE INDEX uq_active_user_show_reservation ON reservations (user_id, showtime_id) WHERE status IN ('ACTIVE','CHECKOUT')")
    op.execute('CREATE INDEX ix_bookings_showtime_id ON bookings (showtime_id)')
    op.execute('CREATE INDEX ix_bookings_user_date ON bookings (user_id, booking_date DESC)')
    op.execute('CREATE INDEX ix_bookings_user_id ON bookings (user_id)')
    op.execute("CREATE INDEX ix_seat_status_hold_expired ON seat_status (hold_expired_at) WHERE status = 'HOLD' AND hold_expired_at IS NOT NULL")
    op.execute('CREATE INDEX ix_seat_status_reservation_id ON seat_status (reservation_id)')
    op.execute('CREATE INDEX ix_seat_status_seat_id ON seat_status (seat_id)')
    op.execute('CREATE INDEX ix_seat_status_showtime_id ON seat_status (showtime_id)')
    op.execute('CREATE INDEX ix_seat_status_showtime_status ON seat_status (showtime_id, status)')
    op.execute('CREATE INDEX ix_booking_details_booking_id ON booking_details (booking_id)')
    op.execute('CREATE INDEX ix_booking_details_seat_id ON booking_details (seat_id)')
    op.execute('CREATE INDEX ix_booking_food_items_booking_id ON booking_food_items (booking_id)')
    op.execute('CREATE INDEX ix_booking_food_items_food_item_id ON booking_food_items (food_item_id)')
    op.execute('CREATE INDEX ix_payments_booking_id ON payments (booking_id)')
    op.execute('CREATE INDEX ix_booking_sales_configurations_film_id ON booking_sales_configurations (film_id)')
    op.execute('CREATE INDEX ix_booking_sales_configurations_room_id ON booking_sales_configurations (room_id)')
    op.execute('CREATE INDEX ix_booking_sales_configurations_theater_id ON booking_sales_configurations (theater_id)')
    migrations_v1.create(op)
    op.execute("""
    CREATE OR REPLACE FUNCTION cinema_validate_booking_seat() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE target_show integer; target_version integer; buyer integer; state text; payload jsonb;
            gate_version integer; gate_open boolean; seat jsonb;
    BEGIN
      state:='service';
      IF TG_TABLE_NAME='booking_details' THEN
        SELECT showtime_id,sales_version,user_id INTO target_show,target_version,buyer FROM bookings WHERE id=NEW.booking_id;
      ELSE target_show:=NEW.showtime_id; target_version:=NEW.sales_version; END IF;
      IF TG_TABLE_NAME='seat_status' THEN
        IF state='maintenance' AND NEW.status='HOLD' THEN
          RAISE EXCEPTION 'Cinema is frozen; no new or extended holds' USING ERRCODE='23514';
        END IF;
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
      state:='service';
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
      state:='service';
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
    op.execute("""
    CREATE FUNCTION booking_sales_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Published sales configuration is immutable'; END $$;
    CREATE TRIGGER immutable_sales_configuration BEFORE UPDATE OR DELETE ON booking_sales_configurations FOR EACH ROW EXECUTE FUNCTION booking_sales_immutable();
    CREATE TRIGGER validate_booking_seat BEFORE INSERT OR UPDATE ON booking_details FOR EACH ROW EXECUTE FUNCTION cinema_validate_booking_seat();
    CREATE TRIGGER validate_status_seat BEFORE INSERT OR UPDATE ON seat_status FOR EACH ROW EXECUTE FUNCTION cinema_validate_booking_seat();
    CREATE TRIGGER validate_ticket BEFORE INSERT OR UPDATE ON tickets FOR EACH ROW EXECUTE FUNCTION cinema_validate_ticket();

    ALTER TABLE bookings ADD CONSTRAINT ck_booking_state CHECK (booking_status IN ('PENDING','CONFIRMED','CANCELLED','EXPIRED') AND payment_status IN ('PENDING','PAID','FAILED','CANCELLED'));
    ALTER TABLE bookings ADD CONSTRAINT ck_booking_currency CHECK (currency='VND' AND booking_version>0);
    ALTER TABLE seat_status ADD CONSTRAINT ck_seat_state CHECK (status IN ('AVAILABLE','HOLD','BOOKED'));
    ALTER TABLE checkout_snapshots ADD CONSTRAINT ck_checkout_amount CHECK (amount>0 AND currency='VND' AND booking_version>0);

    CREATE FUNCTION checkout_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Checkout snapshot is immutable'; END $$;
    CREATE TRIGGER checkout_immutable BEFORE UPDATE OR DELETE ON checkout_snapshots FOR EACH ROW EXECUTE FUNCTION checkout_immutable();
    CREATE TRIGGER food_snapshot_immutable BEFORE UPDATE OR DELETE ON booking_food_items FOR EACH ROW EXECUTE FUNCTION checkout_immutable();
    CREATE TRIGGER detail_snapshot_immutable BEFORE DELETE ON booking_details FOR EACH ROW EXECUTE FUNCTION checkout_immutable();
    CREATE TRIGGER idempotency_immutable BEFORE UPDATE OR DELETE ON booking_idempotency FOR EACH ROW EXECUTE FUNCTION checkout_immutable();

    CREATE FUNCTION booking_checkout_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE r reservations%ROWTYPE;
    BEGIN
      SELECT * INTO r FROM reservations WHERE id=NEW.reservation_id;
      IF NOT FOUND OR r.user_id<>NEW.user_id OR r.showtime_id<>NEW.showtime_id OR r.sales_version<>NEW.sales_version OR r.expires_at IS DISTINCT FROM coalesce(NEW.expires_at,NEW.booking_date+interval '10 minutes') THEN
        RAISE EXCEPTION 'Booking requires the exact owned reservation' USING ERRCODE='23514'; END IF;
      IF TG_OP='INSERT' THEN
        IF r.status<>'ACTIVE' OR r.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'Reservation cannot checkout' USING ERRCODE='23514'; END IF;
      ELSIF (NEW.user_id,NEW.showtime_id,NEW.sales_version,NEW.reservation_id,NEW.total_amount,NEW.currency,NEW.booking_version,NEW.expires_at,NEW.payment_method,NEW.customer_email,NEW.customer_full_name,NEW.customer_phone,NEW.catalog_film_snapshot::text)
        IS DISTINCT FROM (OLD.user_id,OLD.showtime_id,OLD.sales_version,OLD.reservation_id,OLD.total_amount,OLD.currency,OLD.booking_version,OLD.expires_at,OLD.payment_method,OLD.customer_email,OLD.customer_full_name,OLD.customer_phone,OLD.catalog_film_snapshot::text) THEN
        RAISE EXCEPTION 'Checkout financial/customer facts cannot change' USING ERRCODE='23514';
      END IF; RETURN NEW;
    END $$;
    CREATE TRIGGER booking_checkout BEFORE INSERT OR UPDATE ON bookings FOR EACH ROW EXECUTE FUNCTION booking_checkout_guard();

    CREATE FUNCTION reservation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF (NEW.user_id,NEW.showtime_id,NEW.sales_version,NEW.expires_at) IS DISTINCT FROM (OLD.user_id,OLD.showtime_id,OLD.sales_version,OLD.expires_at)
        OR (OLD.status<>'ACTIVE' AND NEW.seat_ids::text IS DISTINCT FROM OLD.seat_ids::text)
        OR (OLD.status IN ('CONFIRMED','EXPIRED','RELEASED') AND NEW.status<>OLD.status) THEN
        RAISE EXCEPTION 'Reservation identity/deadline or sealed seats cannot change' USING ERRCODE='23514'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER reservation_guard BEFORE UPDATE ON reservations FOR EACH ROW EXECUTE FUNCTION reservation_guard();

    CREATE FUNCTION seat_reservation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE r reservations%ROWTYPE;
    BEGIN
      IF TG_OP='UPDATE' THEN
        IF (OLD.status='BOOKED' AND NEW.reservation_id IS DISTINCT FROM OLD.reservation_id)
          OR (NEW.status='BOOKED' AND NEW.reservation_id IS DISTINCT FROM OLD.reservation_id)
          OR (NEW.status='HOLD' AND OLD.status='HOLD' AND OLD.hold_expired_at>clock_timestamp() AND NEW.reservation_id IS DISTINCT FROM OLD.reservation_id) THEN
          RAISE EXCEPTION 'Seat reservation cannot be replaced while held/booked' USING ERRCODE='23514'; END IF;
      END IF;
      IF NEW.status IN ('HOLD','BOOKED') THEN
        SELECT * INTO r FROM reservations WHERE id=NEW.reservation_id;
        IF NOT FOUND OR r.showtime_id<>NEW.showtime_id OR r.sales_version<>NEW.sales_version OR NOT r.seat_ids::jsonb @> to_jsonb(ARRAY[NEW.seat_id]) THEN
          RAISE EXCEPTION 'Seat requires the exact reservation' USING ERRCODE='23514'; END IF;
        IF NEW.status='HOLD' AND (r.status<>'ACTIVE' OR r.user_id IS DISTINCT FROM NEW.hold_by_user_id OR r.expires_at IS DISTINCT FROM NEW.hold_expired_at) THEN
          RAISE EXCEPTION 'Hold cannot extend or change its reservation' USING ERRCODE='23514'; END IF;
        IF NEW.status='BOOKED' AND r.status NOT IN ('CHECKOUT','CONFIRMED') THEN RAISE EXCEPTION 'Seat reservation is not checking out' USING ERRCODE='23514'; END IF;
      END IF; RETURN NEW;
    END $$;
    CREATE TRIGGER seat_reservation BEFORE INSERT OR UPDATE ON seat_status FOR EACH ROW EXECUTE FUNCTION seat_reservation_guard();

    CREATE FUNCTION payment_checkout_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF (NEW.booking_id,NEW.provider,NEW.payment_method,NEW.merchant_ref,NEW.amount,NEW.currency,NEW.checkout_version)
        IS DISTINCT FROM (OLD.booking_id,OLD.provider,OLD.payment_method,OLD.merchant_ref,OLD.amount,OLD.currency,OLD.checkout_version)
        OR (OLD.status='PAID' AND NEW.status<>'PAID') THEN
        RAISE EXCEPTION 'Payment checkout facts or collected result cannot change' USING ERRCODE='23514'; END IF; RETURN NEW;
    END $$;
    CREATE TRIGGER payment_checkout BEFORE UPDATE ON payments FOR EACH ROW EXECUTE FUNCTION payment_checkout_guard();

    CREATE FUNCTION detail_reservation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM bookings b JOIN seat_status s ON s.showtime_id=b.showtime_id AND s.seat_id=NEW.seat_id AND s.reservation_id=b.reservation_id WHERE b.id=NEW.booking_id) THEN
        RAISE EXCEPTION 'Booking detail belongs to another reservation' USING ERRCODE='23514'; END IF; RETURN NEW;
    END $$;
    CREATE TRIGGER detail_reservation BEFORE INSERT ON booking_details FOR EACH ROW EXECUTE FUNCTION detail_reservation_guard();
    """)

def downgrade():
    raise RuntimeError("Do not remove checkout/reservation/payment history")
