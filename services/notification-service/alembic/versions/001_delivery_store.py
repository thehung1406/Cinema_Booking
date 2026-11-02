"""Independent notification delivery store and local inbox.

Schema creation is frozen by this revision before its first release.
"""
from alembic import op
import sqlalchemy as sa
from cinema_platform import migrations_v1
revision = "notification_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    migrations_v1.create(op)
    op.create_table("delivery_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dedup_key", sa.String(150), nullable=False, unique=True),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)))
    for column in ("booking_id", "status", "next_attempt_at"):
        op.create_index("ix_delivery_jobs_" + column, "delivery_jobs", [column])
    op.create_table("delivery_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("delivery_jobs.id"), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("error_type", sa.String(100)),
        sa.Column("actor", sa.String(100)), sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_delivery_attempts_job_id", "delivery_attempts", ["job_id"])


def downgrade():
    op.drop_table("delivery_attempts")
    op.drop_table("delivery_jobs")
    migrations_v1.drop(op)
