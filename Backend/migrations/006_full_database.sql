-- Cinema Booking schema 006: 23 application tables.
-- FRESH DATABASE ONLY. Existing databases: python -m alembic upgrade head.

BEGIN;

CREATE TABLE ai_documents (
	id SERIAL NOT NULL,
	source_id VARCHAR(100) NOT NULL,
	title VARCHAR(200) NOT NULL,
	version VARCHAR(50) NOT NULL,
	source_url VARCHAR(500) NOT NULL,
	approved BOOLEAN NOT NULL,
	effective_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (source_id)
)

;

CREATE TABLE films (
	id SERIAL NOT NULL,
	title VARCHAR(100) NOT NULL,
	image VARCHAR(255),
	rating VARCHAR(10),
	duration_minutes INTEGER,
	language VARCHAR(50),
	subtitle VARCHAR(50),
	deleted_at TIMESTAMP WITH TIME ZONE,
	release_date DATE,
	end_date DATE,
	description TEXT,
	trailer VARCHAR(255),
	PRIMARY KEY (id),
	CONSTRAINT ck_film_duration_positive CHECK (duration_minutes > 0)
)

;

CREATE TABLE formats (
	id SERIAL NOT NULL,
	code VARCHAR(20) NOT NULL,
	name VARCHAR(50) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (code)
)

;

CREATE TABLE genres (
	id SERIAL NOT NULL,
	name VARCHAR(100) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
)

;

CREATE TABLE permissions (
	id SERIAL NOT NULL,
	code VARCHAR(100) NOT NULL,
	name VARCHAR(100) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (code)
)

;

CREATE TABLE roles (
	id SERIAL NOT NULL,
	code VARCHAR(20) NOT NULL,
	name VARCHAR(100) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (code)
)

;

CREATE TABLE theaters (
	id SERIAL NOT NULL,
	name VARCHAR(100) NOT NULL,
	address VARCHAR(255) NOT NULL,
	city VARCHAR(50) NOT NULL,
	image VARCHAR(255),
	rating NUMERIC(3, 1),
	technologies JSONB,
	special VARCHAR(50),
	deleted_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id)
)

;

CREATE TABLE ai_chunks (
	id SERIAL NOT NULL,
	document_id INTEGER NOT NULL,
	content VARCHAR(3000) NOT NULL,
	embedding JSON NOT NULL,
	embedding_version VARCHAR(100) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(document_id) REFERENCES ai_documents (id)
)

;

CREATE TABLE cinema_rooms (
	id SERIAL NOT NULL,
	theater_id INTEGER NOT NULL,
	name VARCHAR(50) NOT NULL,
	capacity INTEGER NOT NULL,
	room_type VARCHAR(50),
	status VARCHAR(20) NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(theater_id) REFERENCES theaters (id) ON DELETE RESTRICT
)

;

CREATE TABLE film_formats (
	film_id INTEGER NOT NULL,
	format_id INTEGER NOT NULL,
	PRIMARY KEY (film_id, format_id),
	FOREIGN KEY(film_id) REFERENCES films (id) ON DELETE CASCADE,
	FOREIGN KEY(format_id) REFERENCES formats (id) ON DELETE RESTRICT
)

;

CREATE TABLE film_genres (
	film_id INTEGER NOT NULL,
	genre_id INTEGER NOT NULL,
	PRIMARY KEY (film_id, genre_id),
	FOREIGN KEY(film_id) REFERENCES films (id) ON DELETE CASCADE,
	FOREIGN KEY(genre_id) REFERENCES genres (id) ON DELETE RESTRICT
)

;

CREATE TABLE role_permissions (
	role_id INTEGER NOT NULL,
	permission_id INTEGER NOT NULL,
	PRIMARY KEY (role_id, permission_id),
	FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE,
	FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE
)

;

CREATE TABLE users (
	id SERIAL NOT NULL,
	username VARCHAR(50) NOT NULL,
	password VARCHAR(100) NOT NULL,
	email VARCHAR(100) NOT NULL,
	phone VARCHAR(15),
	full_name VARCHAR(100),
	avatar VARCHAR(255),
	role_id INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE RESTRICT
)

;

CREATE TABLE reviews (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	film_id INTEGER NOT NULL,
	content VARCHAR(3000) NOT NULL,
	content_version INTEGER NOT NULL,
	moderation_status VARCHAR(20) NOT NULL,
	is_deleted BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_review_user_film UNIQUE (user_id, film_id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(film_id) REFERENCES films (id)
)

;

CREATE TABLE seat_types (
	id SERIAL NOT NULL,
	room_id INTEGER NOT NULL,
	name VARCHAR(30) NOT NULL,
	base_price NUMERIC(12, 2) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_seat_type_room_name UNIQUE (room_id, name),
	FOREIGN KEY(room_id) REFERENCES cinema_rooms (id) ON DELETE RESTRICT
)

;

CREATE TABLE showtimes (
	id SERIAL NOT NULL,
	film_id INTEGER NOT NULL,
	room_id INTEGER NOT NULL,
	show_date DATE NOT NULL,
	start_time TIME WITHOUT TIME ZONE NOT NULL,
	end_time TIME WITHOUT TIME ZONE NOT NULL,
	format_id INTEGER NOT NULL,
	status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_showtime_film_format FOREIGN KEY(film_id, format_id) REFERENCES film_formats (film_id, format_id) ON DELETE RESTRICT,
	FOREIGN KEY(film_id) REFERENCES films (id) ON DELETE RESTRICT,
	FOREIGN KEY(room_id) REFERENCES cinema_rooms (id) ON DELETE RESTRICT,
	FOREIGN KEY(format_id) REFERENCES formats (id) ON DELETE RESTRICT
)

;

CREATE TABLE bookings (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	showtime_id INTEGER NOT NULL,
	booking_date TIMESTAMP WITH TIME ZONE NOT NULL,
	total_amount NUMERIC(12, 2) NOT NULL,
	payment_method VARCHAR(50),
	payment_status VARCHAR(20) DEFAULT 'PENDING' NOT NULL,
	booking_status VARCHAR(20) DEFAULT 'PENDING' NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	CONSTRAINT ck_booking_total_positive CHECK (total_amount > 0),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT,
	FOREIGN KEY(showtime_id) REFERENCES showtimes (id) ON DELETE RESTRICT
)

;

CREATE TABLE review_sentiments (
	review_id INTEGER NOT NULL,
	content_version INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	label VARCHAR(20),
	scores JSON NOT NULL,
	model_version VARCHAR(200),
	attempts INTEGER NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (review_id),
	FOREIGN KEY(review_id) REFERENCES reviews (id)
)

;

CREATE TABLE seats (
	id SERIAL NOT NULL,
	room_id INTEGER NOT NULL,
	seat_type_id INTEGER NOT NULL,
	seat_name VARCHAR(10) NOT NULL,
	status VARCHAR(20) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_seat_room_name UNIQUE (room_id, seat_name),
	FOREIGN KEY(room_id) REFERENCES cinema_rooms (id) ON DELETE RESTRICT,
	FOREIGN KEY(seat_type_id) REFERENCES seat_types (id) ON DELETE RESTRICT
)

;

CREATE TABLE booking_details (
	id SERIAL NOT NULL,
	booking_id INTEGER NOT NULL,
	seat_id INTEGER NOT NULL,
	price NUMERIC(12, 2) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_booking_detail_seat UNIQUE (booking_id, seat_id),
	CONSTRAINT ck_booking_detail_price CHECK (price >= 0),
	FOREIGN KEY(booking_id) REFERENCES bookings (id) ON DELETE RESTRICT,
	FOREIGN KEY(seat_id) REFERENCES seats (id) ON DELETE RESTRICT
)

;

CREATE TABLE payments (
	id SERIAL NOT NULL,
	booking_id INTEGER NOT NULL,
	provider VARCHAR(30) NOT NULL,
	payment_method VARCHAR(50) NOT NULL,
	merchant_ref VARCHAR(100) NOT NULL,
	transaction_ref VARCHAR(100),
	amount NUMERIC(12, 2) NOT NULL,
	currency VARCHAR(3) NOT NULL,
	status VARCHAR(20) NOT NULL,
	paid_at TIMESTAMP WITH TIME ZONE,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_payment_provider_transaction UNIQUE (provider, transaction_ref),
	CONSTRAINT ck_payment_amount_positive CHECK (amount > 0),
	CONSTRAINT ck_payment_status CHECK (status IN ('PENDING','PAID','FAILED','CANCELLED')),
	FOREIGN KEY(booking_id) REFERENCES bookings (id) ON DELETE RESTRICT,
	UNIQUE (merchant_ref)
)

;

CREATE TABLE seat_status (
	id SERIAL NOT NULL,
	seat_id INTEGER NOT NULL,
	showtime_id INTEGER NOT NULL,
	status VARCHAR(20) DEFAULT 'AVAILABLE' NOT NULL,
	version INTEGER DEFAULT '0' NOT NULL,
	hold_by_user_id INTEGER,
	hold_expired_at TIMESTAMP WITH TIME ZONE,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_seat_showtime UNIQUE (showtime_id, seat_id),
	FOREIGN KEY(seat_id) REFERENCES seats (id) ON DELETE RESTRICT,
	FOREIGN KEY(showtime_id) REFERENCES showtimes (id) ON DELETE RESTRICT,
	FOREIGN KEY(hold_by_user_id) REFERENCES users (id) ON DELETE SET NULL
)

;

CREATE TABLE tickets (
	id SERIAL NOT NULL,
	booking_detail_id INTEGER NOT NULL,
	ticket_code VARCHAR(100) NOT NULL,
	status VARCHAR(20) NOT NULL,
	issued_at TIMESTAMP WITH TIME ZONE NOT NULL,
	used_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	CONSTRAINT ck_ticket_status CHECK (status IN ('ISSUED','USED','CANCELLED')),
	UNIQUE (booking_detail_id),
	FOREIGN KEY(booking_detail_id) REFERENCES booking_details (id) ON DELETE RESTRICT,
	UNIQUE (ticket_code)
)

;
CREATE INDEX ix_films_release_end_date ON films (release_date, end_date);
CREATE INDEX ix_ai_chunks_document_id ON ai_chunks (document_id);
CREATE INDEX ix_cinema_rooms_theater_id ON cinema_rooms (theater_id);
CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE INDEX ix_users_role_id ON users (role_id);
CREATE UNIQUE INDEX ix_users_username ON users (username);
CREATE INDEX ix_reviews_film_window ON reviews (film_id, updated_at);
CREATE INDEX ix_seat_types_room_id ON seat_types (room_id);
CREATE INDEX ix_showtimes_film_date_status ON showtimes (film_id, show_date, status);
CREATE INDEX ix_showtimes_film_id ON showtimes (film_id);
CREATE INDEX ix_showtimes_format_id ON showtimes (format_id);
CREATE INDEX ix_showtimes_room_id ON showtimes (room_id);
CREATE INDEX ix_bookings_showtime_id ON bookings (showtime_id);
CREATE INDEX ix_bookings_user_date ON bookings (user_id, booking_date DESC);
CREATE INDEX ix_bookings_user_id ON bookings (user_id);
CREATE INDEX ix_review_sentiments_status ON review_sentiments (status);
CREATE INDEX ix_seats_room_id ON seats (room_id);
CREATE INDEX ix_seats_seat_type_id ON seats (seat_type_id);
CREATE INDEX ix_booking_details_booking_id ON booking_details (booking_id);
CREATE INDEX ix_booking_details_seat_id ON booking_details (seat_id);
CREATE INDEX ix_payments_booking_id ON payments (booking_id);
CREATE INDEX ix_seat_status_hold_expired ON seat_status (hold_expired_at) WHERE status = 'HOLD' AND hold_expired_at IS NOT NULL;
CREATE INDEX ix_seat_status_seat_id ON seat_status (seat_id);
CREATE INDEX ix_seat_status_showtime_id ON seat_status (showtime_id);
CREATE INDEX ix_seat_status_showtime_status ON seat_status (showtime_id, status);

INSERT INTO roles(code,name) VALUES
 ('USER','USER'),('STAFF','STAFF'),('MANAGER','MANAGER'),('ADMIN','ADMIN');
INSERT INTO permissions(code,name) VALUES
 ('tickets.check_in','Kiểm vé'),('reviews.moderate','Duyệt đánh giá'),
 ('seat_types.manage','Quản lý giá và loại ghế'),
 ('users.manage','Gán vai trò người dùng'),('roles.manage','Quản lý phân quyền');
INSERT INTO role_permissions(role_id,permission_id)
 SELECT r.id,p.id FROM roles r CROSS JOIN permissions p
 WHERE r.code='ADMIN' OR (r.code IN ('STAFF','MANAGER')
       AND p.code IN ('tickets.check_in','reviews.moderate','seat_types.manage'));
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
            FOR EACH ROW EXECUTE FUNCTION cinema_validate_ticket();;


CREATE TABLE alembic_version (version_num varchar(32) NOT NULL PRIMARY KEY);
INSERT INTO alembic_version VALUES ('006');
COMMIT;
