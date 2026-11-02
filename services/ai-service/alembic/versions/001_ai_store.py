"""Independent AI store, with no FK to the identity database."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "ai_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ai_conversations",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False), sa.Column("context", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_ai_conversations_user_updated", "ai_conversations", ["user_id", "updated_at"])
    op.create_table("ai_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False), sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_ai_messages_role"))
    op.create_index("ix_ai_messages_conversation_id", "ai_messages", ["conversation_id", "id"])
    op.create_table("ai_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(100), nullable=False, unique=True), sa.Column("title", sa.String(200), nullable=False),
        sa.Column("version", sa.String(50), nullable=False), sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False), sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("ai_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("ai_documents.id"), nullable=False),
        sa.Column("content", sa.String(3000), nullable=False), sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("embedding_version", sa.String(100), nullable=False))
    op.create_index("ix_ai_chunks_document_id", "ai_chunks", ["document_id"])


def downgrade():
    for table in ("ai_chunks", "ai_documents", "ai_messages", "ai_conversations"):
        op.drop_table(table)
