from alembic import op
from cinema_platform.reporting_v1 import install

revision = "payment_002"
down_revision = "payment_001"
branch_labels = None
depends_on = None


def upgrade():
    install(
        op,
        "payment",
        "SELECT 'payment'::text kind,id::text key,jsonb_build_object('id',id,'booking_id',booking_id,'checkout_version',checkout_version,'amount',amount::text,'currency',currency,'status',status) payload FROM payments",
        {"payments": "PERFORM report_touch('payment',COALESCE(NEW.id,OLD.id)::text);"},
    )


def downgrade():
    raise RuntimeError("Retain report generations and tombstones; repair forward")
