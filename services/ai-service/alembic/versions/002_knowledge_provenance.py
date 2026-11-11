"""Source identity and page/section provenance, preserving existing knowledge."""
from alembic import op
import sqlalchemy as sa

revision = "ai_002"
down_revision = "ai_001"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("ai_documents", "ai_chunks"):
        op.add_column(table, sa.Column("provenance", sa.JSON(), nullable=False, server_default="{}"))


def downgrade():
    raise RuntimeError("Knowledge provenance must not be discarded; repair forward")
