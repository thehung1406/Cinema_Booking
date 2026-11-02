"""Independent Review store and immutable initial messaging DDL."""
from cinema_platform import migrations_v1
from alembic import op
import sqlalchemy as sa

revision = "review_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("film_id", sa.Integer(), nullable=False),
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
    op.add_column("reviews", sa.Column("event_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("review_sentiments", sa.Column("analysis_generation", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("review_sentiments", sa.Column("lease_token", sa.String(36)))
    op.add_column("review_sentiments", sa.Column("lease_until", sa.DateTime(timezone=True)))
    migrations_v1.create(op)


def downgrade():
    migrations_v1.drop(op)
    op.drop_table("review_sentiments")
    op.drop_table("reviews")
