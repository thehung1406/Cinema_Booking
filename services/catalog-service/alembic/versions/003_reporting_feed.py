from alembic import op
from cinema_platform.reporting_v1 import install
from cinema_platform import migrations_v1

revision = "catalog_003"
down_revision = "catalog_002"
branch_labels = None
depends_on = None


def upgrade():
    migrations_v1.create(op)
    install(
        op,
        "catalog",
        "SELECT 'film'::text kind,id::text key,jsonb_build_object('id',id,'title',title,'retired',deleted_at IS NOT NULL) payload FROM films",
        {"films": "PERFORM report_touch('film',COALESCE(NEW.id,OLD.id)::text);"},
    )


def downgrade():
    raise RuntimeError("Retain report generations and tombstones; repair forward")
