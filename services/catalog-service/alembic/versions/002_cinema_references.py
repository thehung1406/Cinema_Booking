"""Cinema confirms/releases configuration references; published IDs remain permanent."""
from alembic import op
import sqlalchemy as sa

revision="catalog_002"
down_revision="catalog_001"
branch_labels=None
depends_on=None


def upgrade():
    op.create_table("schedule_binding_closures",sa.Column("id",sa.String(36),primary_key=True),sa.Column("reference",sa.String(100),nullable=False))
    op.add_column("schedule_bindings",sa.Column("reference_state",sa.String(20),nullable=False,server_default="CONFIRMED"))
    op.add_column("schedule_bindings",sa.Column("reference",sa.String(100)))
    for fk in sa.inspect(op.get_bind()).get_foreign_keys("schedule_bindings"):
        if fk["referred_table"]=="film_formats": op.drop_constraint(fk["name"],"schedule_bindings",type_="foreignkey")
    op.create_foreign_key("fk_binding_film","schedule_bindings","films",["film_id"],["id"],ondelete="RESTRICT")
    op.create_foreign_key("fk_binding_format","schedule_bindings","formats",["format_id"],["id"],ondelete="RESTRICT")


def downgrade():
    raise RuntimeError("Released Cinema references require reconciliation before downgrade")
