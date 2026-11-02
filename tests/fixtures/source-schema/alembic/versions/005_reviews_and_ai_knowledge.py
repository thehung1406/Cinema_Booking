"""Reviews, current version sentiments and curated retrieval documents.

Revision ID: 005
Revises: 004
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("film_id", sa.Integer(), sa.ForeignKey("films.id"), nullable=False),
        sa.Column("content", sa.String(3000), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("moderation_status", sa.String(20), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "film_id", name="uq_review_user_film"))
    op.create_index("ix_reviews_film_window", "reviews", ["film_id", "updated_at"])
    op.create_table("review_sentiments",
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("reviews.id"), primary_key=True),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("label", sa.String(20)),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("model_version", sa.String(200)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_review_sentiments_status", "review_sentiments", ["status"])
    op.create_table("ai_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.String(100), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("ai_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("ai_documents.id"), nullable=False),
        sa.Column("content", sa.String(3000), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("embedding_version", sa.String(100), nullable=False))
    op.create_index("ix_ai_chunks_document_id", "ai_chunks", ["document_id"])


def downgrade():
    for name in ("ai_chunks", "ai_documents", "review_sentiments", "reviews"):
        op.drop_table(name)
