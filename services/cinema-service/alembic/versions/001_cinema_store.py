"""Own Cinema store, intra-domain constraints and durable publications."""
from alembic import op

revision="cinema_001"
down_revision=None
branch_labels=None
depends_on=None


def upgrade():
    op.execute('\nCREATE TABLE theaters (\n\tid SERIAL NOT NULL, \n\tname VARCHAR(100) NOT NULL, \n\taddress VARCHAR(255) NOT NULL, \n\tcity VARCHAR(50) NOT NULL, \n\timage VARCHAR(255), \n\trating NUMERIC(3, 1), \n\ttechnologies JSONB, \n\tspecial VARCHAR(50), \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id)\n)\n\n')
    op.execute('\nCREATE TABLE cinema_rooms (\n\tid SERIAL NOT NULL, \n\ttheater_id INTEGER NOT NULL, \n\tname VARCHAR(50) NOT NULL, \n\tcapacity INTEGER NOT NULL, \n\troom_type VARCHAR(50), \n\tstatus VARCHAR(20) NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\toperation_id VARCHAR(36), \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_room_capacity CHECK (capacity BETWEEN 1 AND 2000), \n\tFOREIGN KEY(theater_id) REFERENCES theaters (id) ON DELETE RESTRICT\n)\n\n')
    op.execute('\nCREATE TABLE cinema_operations (\n\tid VARCHAR(36) NOT NULL, \n\troom_id INTEGER NOT NULL, \n\tkind VARCHAR(30) NOT NULL, \n\ttarget_id INTEGER, \n\tpayload JSON NOT NULL, \n\tprogress JSON NOT NULL, \n\tphase VARCHAR(30) NOT NULL, \n\tstatus VARCHAR(30) NOT NULL, \n\tmessage VARCHAR(500) NOT NULL, \n\tresult JSON, \n\tactor_id INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(room_id) REFERENCES cinema_rooms (id) ON DELETE RESTRICT\n)\n\n')
    op.execute('\nCREATE TABLE seat_types (\n\tid SERIAL NOT NULL, \n\troom_id INTEGER NOT NULL, \n\tname VARCHAR(30) NOT NULL, \n\tbase_price NUMERIC(12, 2) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_seat_type_room_name UNIQUE (room_id, name), \n\tCONSTRAINT uq_seat_type_room_id UNIQUE (room_id, id), \n\tCONSTRAINT ck_seat_type_price CHECK (base_price >= 0), \n\tFOREIGN KEY(room_id) REFERENCES cinema_rooms (id) ON DELETE RESTRICT\n)\n\n')
    op.execute("\nCREATE TABLE showtimes (\n\tid SERIAL NOT NULL, \n\tfilm_id INTEGER NOT NULL, \n\troom_id INTEGER NOT NULL, \n\tformat_id INTEGER NOT NULL, \n\tshow_date DATE NOT NULL, \n\tstart_time TIME WITHOUT TIME ZONE NOT NULL, \n\tend_time TIME WITHOUT TIME ZONE NOT NULL, \n\tstatus VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL, \n\tcatalog_binding_id VARCHAR(36), \n\tcatalog_film_snapshot JSON DEFAULT '{}' NOT NULL, \n\tsales_version INTEGER DEFAULT '0' NOT NULL, \n\tcontrol_epoch INTEGER DEFAULT '0' NOT NULL, \n\tsales_state VARCHAR(30) DEFAULT 'CLOSED' NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_showtime_interval CHECK (end_time > start_time), \n\tFOREIGN KEY(room_id) REFERENCES cinema_rooms (id) ON DELETE RESTRICT\n)\n\n")
    op.execute('\nCREATE TABLE sales_publications (\n\tshowtime_id INTEGER NOT NULL, \n\tsales_version INTEGER NOT NULL, \n\tdigest VARCHAR(64) NOT NULL, \n\tsnapshot JSON NOT NULL, \n\tacknowledged BOOLEAN NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (showtime_id, sales_version), \n\tFOREIGN KEY(showtime_id) REFERENCES showtimes (id) ON DELETE RESTRICT\n)\n\n')
    op.execute('\nCREATE TABLE seats (\n\tid SERIAL NOT NULL, \n\troom_id INTEGER NOT NULL, \n\tseat_type_id INTEGER NOT NULL, \n\tseat_name VARCHAR(10) NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(room_id, seat_type_id) REFERENCES seat_types (room_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(room_id) REFERENCES cinema_rooms (id) ON DELETE RESTRICT\n)\n\n')
    op.execute('CREATE INDEX ix_cinema_rooms_theater_id ON cinema_rooms (theater_id)')
    op.execute('CREATE UNIQUE INDEX uq_live_room_theater_name ON cinema_rooms (theater_id, name) WHERE deleted_at IS NULL')
    op.execute('CREATE INDEX ix_cinema_operations_room_id ON cinema_operations (room_id)')
    op.execute('CREATE INDEX ix_cinema_operations_status ON cinema_operations (status)')
    op.execute('CREATE INDEX ix_seat_types_room_id ON seat_types (room_id)')
    op.execute('CREATE INDEX ix_showtimes_film_date_status ON showtimes (film_id, show_date, status)')
    op.execute('CREATE INDEX ix_showtimes_film_id ON showtimes (film_id)')
    op.execute('CREATE INDEX ix_showtimes_format_id ON showtimes (format_id)')
    op.execute('CREATE INDEX ix_showtimes_room_id ON showtimes (room_id)')
    op.execute('CREATE INDEX ix_seats_room_id ON seats (room_id)')
    op.execute('CREATE INDEX ix_seats_seat_type_id ON seats (seat_type_id)')
    op.execute('CREATE UNIQUE INDEX uq_seat_room_name ON seats (room_id, seat_name) WHERE deleted_at IS NULL')
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public")
    op.execute("""
    ALTER TABLE showtimes ADD CONSTRAINT no_room_schedule_overlap EXCLUDE USING gist
      (room_id WITH =, tsrange(show_date+start_time,show_date+end_time,'[)') WITH &&)
      WHERE (deleted_at IS NULL AND status <> 'CANCELLED');
    CREATE FUNCTION cinema_seat_capacity() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE cap integer; used integer;
    BEGIN
      SELECT capacity INTO cap FROM cinema_rooms WHERE id=NEW.room_id FOR UPDATE;
      SELECT count(*) INTO used FROM seats WHERE room_id=NEW.room_id AND deleted_at IS NULL
        AND id IS DISTINCT FROM NEW.id;
      IF NEW.deleted_at IS NULL AND used>=cap THEN RAISE EXCEPTION 'Room capacity exceeded' USING ERRCODE='23514'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER seat_capacity BEFORE INSERT OR UPDATE ON seats FOR EACH ROW EXECUTE FUNCTION cinema_seat_capacity();
    CREATE FUNCTION cinema_room_capacity() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.capacity < (SELECT count(*) FROM seats WHERE room_id=NEW.id AND deleted_at IS NULL) THEN
        RAISE EXCEPTION 'Room capacity below seat count' USING ERRCODE='23514';
      END IF; RETURN NEW;
    END $$;
    CREATE TRIGGER room_capacity BEFORE UPDATE ON cinema_rooms FOR EACH ROW EXECUTE FUNCTION cinema_room_capacity();
    CREATE FUNCTION cinema_publication_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='DELETE' OR (NEW.showtime_id,NEW.sales_version,NEW.digest,NEW.snapshot::text,NEW.created_at)
        IS DISTINCT FROM (OLD.showtime_id,OLD.sales_version,OLD.digest,OLD.snapshot::text,OLD.created_at)
        OR (OLD.acknowledged AND NOT NEW.acknowledged) THEN
        RAISE EXCEPTION 'Publication is immutable'; END IF; RETURN NEW;
    END $$;
    CREATE TRIGGER publication_immutable BEFORE UPDATE OR DELETE ON sales_publications
      FOR EACH ROW EXECUTE FUNCTION cinema_publication_immutable();
    """)


def downgrade():
    raise RuntimeError("Published configurations require explicit reconciliation")
