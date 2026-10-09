"""Normalize films, add payment attempts, tickets and database-backed permissions.

Revision ID: 006
Revises: 005
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("genres", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("name", sa.String(100), nullable=False, unique=True))
    op.create_table("formats", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("code", sa.String(20), nullable=False, unique=True),
                    sa.Column("name", sa.String(50), nullable=False))
    op.create_table("film_genres",
        sa.Column("film_id", sa.Integer(), sa.ForeignKey("films.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("genre_id", sa.Integer(), sa.ForeignKey("genres.id", ondelete="RESTRICT"), primary_key=True))
    op.create_table("film_formats",
        sa.Column("film_id", sa.Integer(), sa.ForeignKey("films.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("format_id", sa.Integer(), sa.ForeignKey("formats.id", ondelete="RESTRICT"), primary_key=True))
    op.execute("""
        INSERT INTO genres(name)
        SELECT DISTINCT trim(value) FROM films,
             LATERAL regexp_split_to_table(COALESCE(genre, ''), ',') value
        WHERE trim(value) <> '' ORDER BY 1;
        INSERT INTO film_genres(film_id, genre_id)
        SELECT DISTINCT f.id, g.id FROM films f,
             LATERAL regexp_split_to_table(COALESCE(f.genre, ''), ',') value
        JOIN genres g ON g.name = trim(value);
    """)
    # Collect every supported JSON value and every scheduled format, without
    # discarding legacy labels such as IMAX 3D or 2D Standard.
    op.execute("""
        CREATE TEMP TABLE cinema_format_backfill ON COMMIT DROP AS
        SELECT f.id AS film_id, trim(v.label) AS label FROM films f
        CROSS JOIN LATERAL (
            SELECT key AS label FROM jsonb_each(
                CASE WHEN jsonb_typeof(f.formats)='object' THEN f.formats ELSE '{}'::jsonb END)
            WHERE value NOT IN ('false'::jsonb, 'null'::jsonb, '0'::jsonb, '""'::jsonb)
            UNION ALL
            SELECT jsonb_array_elements_text(
                CASE WHEN jsonb_typeof(f.formats)='array' THEN f.formats ELSE '[]'::jsonb END)
            UNION ALL
            SELECT f.formats #>> '{}' WHERE jsonb_typeof(f.formats)='string'
        ) v WHERE trim(v.label) <> ''
        UNION SELECT film_id, trim(format) FROM showtimes;
        INSERT INTO formats(code, name)
        SELECT upper(label), min(label) FROM cinema_format_backfill
        GROUP BY upper(label) ORDER BY upper(label);
        INSERT INTO film_formats(film_id, format_id)
        SELECT DISTINCT b.film_id, f.id FROM cinema_format_backfill b
        JOIN formats f ON f.code=upper(b.label);
    """)
    op.add_column("showtimes", sa.Column("format_id", sa.Integer()))
    op.execute("UPDATE showtimes s SET format_id=f.id FROM formats f WHERE f.code=upper(trim(s.format))")
    op.alter_column("showtimes", "format_id", nullable=False)
    op.create_foreign_key("showtimes_format_id_fkey", "showtimes", "formats", ["format_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_showtime_film_format", "showtimes", "film_formats",
                          ["film_id", "format_id"], ["film_id", "format_id"], ondelete="RESTRICT")
    op.create_index("ix_showtimes_format_id", "showtimes", ["format_id"])
    op.add_column("films", sa.Column("duration_minutes", sa.Integer()))
    op.execute(r"""
        UPDATE films SET duration_minutes = CASE
            WHEN duration ~* '^\s*[0-9]+\s*(phút|min|minutes)?\s*$'
                THEN substring(duration FROM '[0-9]+')::integer
            WHEN duration ~* '^\s*[0-9]+\s*(h|giờ)\s*([0-9]+\s*(phút|min|minutes)?)?\s*$'
                THEN (regexp_match(duration, '([0-9]+)\s*(h|giờ)', 'i'))[1]::integer * 60
                     + COALESCE((regexp_match(duration, '(h|giờ)\s*([0-9]+)', 'i'))[2]::integer, 0)
            WHEN duration ~ '^\s*[0-9]+:[0-5][0-9]\s*$'
                THEN split_part(trim(duration), ':', 1)::integer * 60
                     + split_part(trim(duration), ':', 2)::integer
            ELSE NULL END;
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM films WHERE NULLIF(trim(duration), '') IS NOT NULL
                       AND (duration_minutes IS NULL OR duration_minutes <= 0)) THEN
                RAISE EXCEPTION 'Unrecognized film duration: correct legacy duration before migration 006';
            END IF;
        END $$;
    """)
    op.create_check_constraint("ck_film_duration_positive", "films", "duration_minutes > 0")
    op.drop_column("films", "genre")
    op.drop_column("films", "formats")
    op.drop_column("films", "duration")
    op.drop_column("showtimes", "format")

    op.create_table("roles", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("code", sa.String(20), nullable=False, unique=True),
                    sa.Column("name", sa.String(100), nullable=False))
    op.create_table("permissions", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("code", sa.String(100), nullable=False, unique=True),
                    sa.Column("name", sa.String(100), nullable=False))
    op.create_table("role_permissions",
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True))
    op.execute("""
        INSERT INTO roles(code, name)
        SELECT code, code FROM (
            SELECT DISTINCT role AS code FROM users
            UNION SELECT unnest(ARRAY['USER','STAFF','MANAGER','ADMIN'])
        ) r ORDER BY code;
        INSERT INTO permissions(code, name) VALUES
          ('tickets.check_in', 'Kiểm vé'), ('reviews.moderate', 'Duyệt đánh giá'),
          ('seat_types.manage', 'Quản lý giá và loại ghế'),
          ('users.manage', 'Gán vai trò người dùng'), ('roles.manage', 'Quản lý phân quyền');
        INSERT INTO role_permissions(role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.code='ADMIN' OR (r.code IN ('STAFF','MANAGER')
              AND p.code IN ('tickets.check_in','reviews.moderate','seat_types.manage'));
    """)
    op.add_column("users", sa.Column("role_id", sa.Integer()))
    op.execute("UPDATE users u SET role_id=r.id FROM roles r WHERE u.role=r.code")
    op.alter_column("users", "role_id", nullable=False)
    op.create_foreign_key("users_role_id_fkey", "users", "roles", ["role_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_users_role_id", "users", ["role_id"])
    op.drop_column("users", "role")

    for table in ("films", "theaters", "cinema_rooms"):
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True)))
    for table in ("cinema_rooms", "seats"):
        op.add_column(table, sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"))
        op.alter_column(table, "status", server_default=None)
    op.add_column("bookings", sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE bookings SET expires_at=booking_date + INTERVAL '10 minutes' WHERE booking_status='PENDING'")
    op.execute("UPDATE bookings SET payment_status='PAID' WHERE payment_status='SUCCESS'")
    op.create_unique_constraint("uq_seat_room_name", "seats", ["room_id", "seat_name"])
    op.drop_index("uq_seat_type_room_name", table_name="seat_types")
    op.create_unique_constraint("uq_seat_type_room_name", "seat_types", ["room_id", "name"])
    op.create_unique_constraint("uq_booking_detail_seat", "booking_details", ["booking_id", "seat_id"])
    op.create_check_constraint("ck_booking_detail_price", "booking_details", "price >= 0")
    op.create_check_constraint("ck_booking_total_positive", "bookings", "total_amount > 0")

    # Booking/payment history must never be removed through a cascading catalog delete.
    for table, column, parent in (
        ("cinema_rooms", "theater_id", "theaters"), ("seats", "room_id", "cinema_rooms"),
        ("seat_types", "room_id", "cinema_rooms"), ("showtimes", "film_id", "films"),
        ("showtimes", "room_id", "cinema_rooms"), ("seat_status", "seat_id", "seats"),
        ("seat_status", "showtime_id", "showtimes"), ("bookings", "showtime_id", "showtimes"),
        ("booking_details", "booking_id", "bookings"), ("booking_details", "seat_id", "seats"),
    ):
        name = f"{table}_{column}_fkey"
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(name, table, parent, [column], ["id"], ondelete="RESTRICT")

    op.create_table("payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("payment_method", sa.String(50), nullable=False),
        sa.Column("merchant_ref", sa.String(100), nullable=False, unique=True),
        sa.Column("transaction_ref", sa.String(100)),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "transaction_ref", name="uq_payment_provider_transaction"),
        sa.CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        sa.CheckConstraint("status IN ('PENDING','PAID','FAILED','CANCELLED')", name="ck_payment_status"))
    op.create_index("ix_payments_booking_id", "payments", ["booking_id"])
    op.create_table("tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_detail_id", sa.Integer(), sa.ForeignKey("booking_details.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("ticket_code", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('ISSUED','USED','CANCELLED')", name="ck_ticket_status"))
    op.execute("""
        INSERT INTO payments(booking_id, provider, payment_method, merchant_ref, amount,
                             currency, status, paid_at, created_at, updated_at)
        SELECT id, CASE WHEN upper(COALESCE(payment_method,''))='VNPAY' THEN 'VNPAY' ELSE 'LEGACY' END,
               COALESCE(payment_method,'UNKNOWN'), id::text, total_amount, 'VND',
               CASE WHEN payment_status IN ('PAID','FAILED','CANCELLED') THEN payment_status ELSE 'PENDING' END,
               CASE WHEN payment_status='PAID' THEN booking_date ELSE NULL END, created_at, created_at
        FROM bookings;
        INSERT INTO tickets(booking_detail_id, ticket_code, status, issued_at)
        SELECT d.id, md5(random()::text || clock_timestamp()::text || d.id::text), 'ISSUED', b.booking_date
        FROM booking_details d JOIN bookings b ON b.id=d.booking_id
        WHERE b.payment_status='PAID' AND b.booking_status='CONFIRMED';
    """)
    _install_integrity_triggers()


def _install_integrity_triggers():
    op.execute("""
        CREATE FUNCTION cinema_validate_seat() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM seat_types WHERE id=NEW.seat_type_id AND room_id=NEW.room_id) THEN
                RAISE EXCEPTION 'Seat type belongs to another room' USING ERRCODE='23514';
            END IF;
            IF TG_OP='UPDATE' AND NEW.room_id <> OLD.room_id AND (
                EXISTS (SELECT 1 FROM seat_status WHERE seat_id=NEW.id) OR
                EXISTS (SELECT 1 FROM booking_details WHERE seat_id=NEW.id)) THEN
                RAISE EXCEPTION 'Cannot move a seat with booking history' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER validate_seat BEFORE INSERT OR UPDATE ON seats
            FOR EACH ROW EXECUTE FUNCTION cinema_validate_seat();

        CREATE FUNCTION cinema_validate_seat_type() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.room_id <> OLD.room_id AND EXISTS (SELECT 1 FROM seats WHERE seat_type_id=NEW.id) THEN
                RAISE EXCEPTION 'Cannot move an assigned seat type' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER validate_seat_type BEFORE UPDATE ON seat_types
            FOR EACH ROW EXECUTE FUNCTION cinema_validate_seat_type();

        CREATE FUNCTION cinema_validate_booking_seat() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE target_showtime integer;
        BEGIN
            IF TG_TABLE_NAME='booking_details' THEN
                SELECT showtime_id INTO target_showtime FROM bookings WHERE id=NEW.booking_id;
            ELSE target_showtime := NEW.showtime_id;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM seats s JOIN showtimes st ON st.room_id=s.room_id
                           WHERE s.id=NEW.seat_id AND st.id=target_showtime) THEN
                RAISE EXCEPTION 'Seat does not belong to the showtime room' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER validate_booking_seat BEFORE INSERT OR UPDATE ON booking_details
            FOR EACH ROW EXECUTE FUNCTION cinema_validate_booking_seat();
        CREATE TRIGGER validate_status_seat BEFORE INSERT OR UPDATE ON seat_status
            FOR EACH ROW EXECUTE FUNCTION cinema_validate_booking_seat();

        CREATE FUNCTION cinema_validate_booking_update() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.showtime_id <> OLD.showtime_id AND EXISTS (SELECT 1 FROM booking_details WHERE booking_id=NEW.id) THEN
                RAISE EXCEPTION 'Cannot move a booking with seat details' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER validate_booking_update BEFORE UPDATE ON bookings
            FOR EACH ROW EXECUTE FUNCTION cinema_validate_booking_update();

        CREATE FUNCTION cinema_validate_showtime() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE starts timestamp; ends timestamp;
        BEGIN
            PERFORM pg_advisory_xact_lock(7300, NEW.room_id);
            IF TG_OP='UPDATE' AND NEW.room_id <> OLD.room_id AND (
                EXISTS (SELECT 1 FROM bookings WHERE showtime_id=NEW.id) OR
                EXISTS (SELECT 1 FROM seat_status WHERE showtime_id=NEW.id)) THEN
                RAISE EXCEPTION 'Cannot move a showtime with booking history' USING ERRCODE='23514';
            END IF;
            starts := NEW.show_date + NEW.start_time;
            ends := NEW.show_date + NEW.end_time + CASE WHEN NEW.end_time <= NEW.start_time
                    THEN INTERVAL '1 day' ELSE INTERVAL '0 days' END;
            IF NEW.status='ACTIVE' AND EXISTS (
                SELECT 1 FROM showtimes s WHERE s.room_id=NEW.room_id AND s.status='ACTIVE'
                AND s.id IS DISTINCT FROM NEW.id
                AND tsrange(s.show_date+s.start_time,
                    s.show_date+s.end_time + CASE WHEN s.end_time <= s.start_time
                    THEN INTERVAL '1 day' ELSE INTERVAL '0 days' END, '[)') && tsrange(starts, ends, '[)')
            ) THEN RAISE EXCEPTION 'Overlapping showtimes in the same room' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER validate_showtime BEFORE INSERT OR UPDATE ON showtimes
            FOR EACH ROW EXECUTE FUNCTION cinema_validate_showtime();

        CREATE FUNCTION cinema_validate_ticket() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM booking_details d JOIN bookings b ON b.id=d.booking_id
                           WHERE d.id=NEW.booking_detail_id AND b.payment_status='PAID'
                           AND b.booking_status='CONFIRMED') THEN
                RAISE EXCEPTION 'Ticket requires a paid, confirmed booking' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER validate_ticket BEFORE INSERT OR UPDATE ON tickets
            FOR EACH ROW EXECUTE FUNCTION cinema_validate_ticket();
    """)


def downgrade():
    raise RuntimeError("Migration 006 contains payment/ticket history. Restore a verified backup instead of dropping this data.")
