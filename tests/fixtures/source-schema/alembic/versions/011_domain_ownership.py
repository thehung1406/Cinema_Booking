"""Durable ownership fence for service extraction.

Revision ID: 011
Revises: 010
"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("domain_ownership",
        sa.Column("domain", sa.String(100), primary_key=True),
        sa.Column("owner", sa.String(20), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("domain_ownership_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("domain", sa.String(100), nullable=False),
        sa.Column("old_owner", sa.String(20), nullable=False), sa.Column("new_owner", sa.String(20), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False), sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.execute("INSERT INTO domain_ownership(domain,owner,updated_at) VALUES ('ai','monolith',CURRENT_TIMESTAMP)")


def downgrade():
    # Never reopen an archived writer as an automatic schema downgrade.
    owner = op.get_bind().execute(sa.text("SELECT owner FROM domain_ownership WHERE domain='ai'")).scalar()
    if owner != "monolith":
        raise RuntimeError("Ownership transferred/frozen; explicit data reconciliation required before downgrade")
    op.drop_table("domain_ownership_audits")
    op.drop_table("domain_ownership")
