"""Versioned staff decisions, preserving original model scores and predictions."""
from alembic import op
import sqlalchemy as sa

revision = "review_003"
down_revision = "review_002"
branch_labels = None
depends_on = None


def upgrade():
    for name, type_ in [("predicted_label", sa.String(20)), ("decision_source", sa.String(20)),
                        ("confirmed_by_user_id", sa.Integer()), ("confirmed_at", sa.DateTime(timezone=True)),
                        ("confirmation_note", sa.String(1000))]:
        op.add_column("review_sentiments", sa.Column(name, type_, nullable=True))
    op.execute("UPDATE review_sentiments SET predicted_label=label, decision_source='model' "
               "WHERE model_version IS NOT NULL AND status IN ('succeeded','needs_review')")
    op.create_table("sentiment_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("analysis_generation", sa.Integer(), nullable=False),
        sa.Column("previous_label", sa.String(20)),
        sa.Column("label", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("actor_user_id", "request_id", name="uq_sentiment_decision_request"))
    op.create_index("ix_sentiment_decisions_review_id", "sentiment_decisions", ["review_id"])


def downgrade():
    raise RuntimeError("Retain staff decision audit; repair forward rather than discard decisions")
