"""Register the Review extraction fence.

Revision ID: 012
Revises: 011
"""
from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("INSERT INTO domain_ownership(domain,owner,updated_at) VALUES ('review','monolith',CURRENT_TIMESTAMP)")


def downgrade():
    owner = op.get_bind().execute(sa.text("SELECT owner FROM domain_ownership WHERE domain='review'")).scalar()
    if owner != "monolith":
        raise RuntimeError("Frozen/transferred Review requires explicit reconciliation before downgrade")
    op.execute("DELETE FROM domain_ownership WHERE domain='review'")
