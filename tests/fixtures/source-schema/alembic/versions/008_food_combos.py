"""Add food catalog, combo contents and booking food snapshots.

Revision ID: 008
Revises: 007
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("food_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("price > 0", name="ck_food_price"),
        sa.CheckConstraint("category IN ('POPCORN', 'DRINK', 'COMBO')", name="ck_food_category"),
    )
    op.create_table("combo_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("combo_id", sa.Integer(), sa.ForeignKey("food_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("food_item_id", sa.Integer(), sa.ForeignKey("food_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.UniqueConstraint("combo_id", "food_item_id", name="uq_combo_component"),
        sa.CheckConstraint("quantity > 0", name="ck_combo_quantity"),
        sa.CheckConstraint("combo_id <> food_item_id", name="ck_combo_not_self"),
    )
    op.create_table("booking_food_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("food_item_id", sa.Integer(), sa.ForeignKey("food_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("components", sa.JSON(), nullable=False),
        sa.UniqueConstraint("booking_id", "food_item_id", name="uq_booking_food"),
        sa.CheckConstraint("quantity BETWEEN 1 AND 20", name="ck_booking_food_quantity"),
        sa.CheckConstraint("unit_price > 0", name="ck_booking_food_price"),
    )
    for table, columns in [("combo_items", ["combo_id", "food_item_id"]),
                           ("booking_food_items", ["booking_id", "food_item_id"])]:
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])
    seed_menu()


def seed_menu():
    foods = sa.table("food_items", sa.column("id", sa.Integer()),
        sa.column("name", sa.String()), sa.column("description", sa.String()),
        sa.column("category", sa.String()), sa.column("price", sa.Numeric()),
        sa.column("is_active", sa.Boolean()))
    combos = sa.table("combo_items", sa.column("combo_id", sa.Integer()),
        sa.column("food_item_id", sa.Integer()), sa.column("quantity", sa.Integer()))
    # Sample menu and prices; replace with the cinema's real menu before release.
    op.bulk_insert(foods, [
        dict(id=1, name="Bỏng ngọt lớn", description="Một phần bỏng ngọt cỡ lớn", category="POPCORN", price=55000, is_active=True),
        dict(id=2, name="Bỏng phô mai lớn", description="Một phần bỏng phô mai cỡ lớn", category="POPCORN", price=65000, is_active=True),
        dict(id=3, name="Nước ngọt lớn", description="Một ly nước ngọt cỡ lớn", category="DRINK", price=35000, is_active=True),
        dict(id=4, name="Nước suối", description="Một chai nước suối", category="DRINK", price=20000, is_active=True),
        dict(id=5, name="Combo một người", description="1 bỏng ngọt lớn + 1 nước ngọt lớn", category="COMBO", price=80000, is_active=True),
        dict(id=6, name="Combo hai người", description="1 bỏng ngọt lớn + 2 nước ngọt lớn", category="COMBO", price=110000, is_active=True),
        dict(id=7, name="Combo phô mai", description="1 bỏng phô mai lớn + 2 nước ngọt lớn", category="COMBO", price=120000, is_active=True),
    ])
    op.bulk_insert(combos, [
        dict(combo_id=5, food_item_id=1, quantity=1), dict(combo_id=5, food_item_id=3, quantity=1),
        dict(combo_id=6, food_item_id=1, quantity=1), dict(combo_id=6, food_item_id=3, quantity=2),
        dict(combo_id=7, food_item_id=2, quantity=1), dict(combo_id=7, food_item_id=3, quantity=2),
    ])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("SELECT setval(pg_get_serial_sequence('food_items', 'id'), (SELECT MAX(id) FROM food_items))")


def downgrade():
    op.drop_table("booking_food_items")
    op.drop_table("combo_items")
    op.drop_table("food_items")
