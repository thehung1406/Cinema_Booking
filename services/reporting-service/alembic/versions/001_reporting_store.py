from alembic import op
from cinema_platform import migrations_v1

revision = "reporting_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """CREATE TABLE report_facts(source varchar(30) NOT NULL,kind varchar(30) NOT NULL,key varchar(100) NOT NULL,
        version bigint NOT NULL,deleted boolean NOT NULL,fact json NOT NULL,sha256 varchar(64) NOT NULL,
        received_at timestamptz NOT NULL,PRIMARY KEY(source,kind,key));
        CREATE TABLE report_sources(source varchar(30) PRIMARY KEY,generation varchar(36) NOT NULL,
        bootstrapped boolean NOT NULL,snapshot_id varchar(36),snapshot_sha256 varchar(64),snapshot_at timestamptz,
        checkpoint_version bigint NOT NULL,checkpoint_at timestamptz,verified_at timestamptz,observed_at timestamptz NOT NULL);"""
    )
    migrations_v1.create(op)


def downgrade():
    raise RuntimeError("Preserve reporting checkpoints and generations")
