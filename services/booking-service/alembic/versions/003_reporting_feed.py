from alembic import op
from cinema_platform.reporting_v1 import install

revision = "booking_003"
down_revision = "booking_002"
branch_labels = None
depends_on = None


def upgrade():
    install(
        op,
        "booking",
        """
SELECT 'booking'::text kind,b.id::text key,jsonb_build_object(
 'id',b.id,'showtime_id',b.showtime_id,'sales_version',b.sales_version,'total_amount',b.total_amount::text,
 'booking_status',b.booking_status,'payment_status',b.payment_status,
 'accepted_checkout_version',(SELECT p.booking_version FROM booking_payment_receipts p WHERE p.booking_id=b.id AND p.outcome='CONFIRMED' LIMIT 1),
 'accepted_payment_id',(SELECT p.payment_id FROM booking_payment_receipts p WHERE p.booking_id=b.id AND p.outcome='CONFIRMED' LIMIT 1),
 'seats',COALESCE((SELECT jsonb_agg(jsonb_build_object('seat_id',d.seat_id,'valid_ticket',EXISTS(SELECT 1 FROM tickets t WHERE t.booking_detail_id=d.id AND t.status IN ('ISSUED','USED')))) FROM booking_details d WHERE d.booking_id=b.id),'[]'::jsonb)) payload FROM bookings b
UNION ALL SELECT 'config',c.showtime_id::text||':'||c.sales_version::text,jsonb_build_object('showtime_id',c.showtime_id,'sales_version',c.sales_version,'film_id',c.film_id,'theater_id',c.theater_id,'show_date',c.show_date,'status',c.status,'active_seat_ids',COALESCE((SELECT jsonb_agg((s->>'id')::int ORDER BY (s->>'id')::int) FROM jsonb_array_elements(c.snapshot::jsonb->'seats') s WHERE s->>'status'='ACTIVE'),'[]'::jsonb)) FROM booking_sales_configurations c
UNION ALL SELECT 'gate',showtime_id::text,jsonb_build_object('showtime_id',showtime_id,'sales_version',sales_version) FROM booking_sales_gates
UNION ALL SELECT 'booked_seats',showtime_id::text,jsonb_build_object('showtime_id',showtime_id,'seat_ids',jsonb_agg(seat_id ORDER BY seat_id)) FROM seat_status WHERE status='BOOKED' GROUP BY showtime_id
""",
        {
            "bookings": "PERFORM report_touch('booking',COALESCE(NEW.id,OLD.id)::text);",
            "booking_details": "PERFORM report_touch('booking',COALESCE(NEW.booking_id,OLD.booking_id)::text);",
            "booking_payment_receipts": "PERFORM report_touch('booking',COALESCE(NEW.booking_id,OLD.booking_id)::text);",
            "booking_sales_configurations": "PERFORM report_touch('config',COALESCE(NEW.showtime_id,OLD.showtime_id)::text||':'||COALESCE(NEW.sales_version,OLD.sales_version)::text);",
            "booking_sales_gates": "PERFORM report_touch('gate',COALESCE(NEW.showtime_id,OLD.showtime_id)::text);",
            "seat_status": "IF TG_OP='DELETE' OR OLD.status='BOOKED' OR NEW.status='BOOKED' THEN PERFORM report_touch('booked_seats',COALESCE(NEW.showtime_id,OLD.showtime_id)::text); END IF;",
            "tickets": "PERFORM report_touch('booking',(SELECT booking_id::text FROM booking_details WHERE id=COALESCE(NEW.booking_detail_id,OLD.booking_detail_id)));",
        },
    )


def downgrade():
    raise RuntimeError("Retain report generations and tombstones; repair forward")
