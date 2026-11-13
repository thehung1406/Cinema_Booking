"""Stage source revisions independently of the currently served document."""
from alembic import op
import sqlalchemy as sa

revision = "ai_003"
down_revision = "ai_002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_knowledge_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("ai_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("base_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("published_by", sa.Integer()),
        sa.UniqueConstraint("document_id", "version", name="uq_ai_knowledge_revision_version"),
    )


def downgrade():
    raise RuntimeError("Published knowledge history must not be discarded; repair forward")
