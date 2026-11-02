from alembic import op
from cinema_platform.reporting_v1 import install
from cinema_platform import migrations_v1

revision = "cinema_002"
down_revision = "cinema_001"
branch_labels = None
depends_on = None


def upgrade():
    migrations_v1.create(op)
    install(
        op,
        "cinema",
        "SELECT 'showtime'::text kind,s.id::text key,jsonb_build_object('id',s.id,'film_id',s.film_id,'room_id',s.room_id,'show_date',s.show_date,'status',s.status,'sales_version',s.sales_version) payload FROM showtimes s",
        {
            "showtimes": "PERFORM report_touch('showtime',COALESCE(NEW.id,OLD.id)::text);"
        },
    )


def downgrade():
    raise RuntimeError("Retain report generations and tombstones; repair forward")
