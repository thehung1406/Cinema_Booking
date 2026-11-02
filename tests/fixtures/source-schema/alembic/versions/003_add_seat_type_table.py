"""Add seat_types table, migrate data from seats

Revision ID: 003
Revises: 002
Create Date: 2026-08-17 15:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, Sequence[str], None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Tạo bảng seat_types, migrate data từ seats, drop cột cũ."""

    # ── 1. Tạo bảng seat_types ──
    op.create_table(
        "seat_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=30), nullable=False),
        sa.Column("base_price", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["cinema_rooms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_seat_types_room_id"), "seat_types", ["room_id"]
    )
    # Composite unique: mỗi phòng chỉ có 1 loại ghế cùng tên
    op.create_index(
        "uq_seat_type_room_name", "seat_types", ["room_id", "name"], unique=True
    )

    # ── 2. Migrate data: tạo seat_types từ data hiện có trong seats ──
    # Lấy tất cả (room_id, seat_type) unique, lấy MAX(price) làm base_price
    conn = op.get_bind()
    conn.execute(sa.text("""
        INSERT INTO seat_types (room_id, name, base_price)
        SELECT room_id, seat_type, MAX(price)
        FROM seats
        GROUP BY room_id, seat_type
    """))

    # ── 3. Thêm cột seat_type_id vào seats (nullable tạm) ──
    op.add_column(
        "seats",
        sa.Column("seat_type_id", sa.Integer(), nullable=True),
    )

    # ── 4. Backfill seat_type_id từ seat_types ──
    conn.execute(sa.text("""
        UPDATE seats s
        SET seat_type_id = st.id
        FROM seat_types st
        WHERE s.room_id = st.room_id AND s.seat_type = st.name
    """))

    # ── 5. Set NOT NULL + FK + index trên seat_type_id ──
    op.alter_column("seats", "seat_type_id", nullable=False)
    op.create_foreign_key(
        "seats_seat_type_id_fkey", "seats",
        "seat_types", ["seat_type_id"], ["id"],
        ondelete="RESTRICT"
    )
    op.create_index(
        op.f("ix_seats_seat_type_id"), "seats", ["seat_type_id"]
    )

    # ── 6. Drop cột cũ ──
    op.drop_column("seats", "seat_type")
    op.drop_column("seats", "price")


def downgrade() -> None:
    """Rollback: khôi phục cột seat_type + price, xóa bảng seat_types."""

    # Thêm lại cột cũ (nullable tạm để backfill)
    op.add_column(
        "seats",
        sa.Column("seat_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "seats",
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
    )

    # Backfill từ seat_types
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE seats s
        SET seat_type = st.name,
            price = st.base_price
        FROM seat_types st
        WHERE s.seat_type_id = st.id
    """))

    # Set NOT NULL
    op.alter_column("seats", "seat_type", nullable=False)
    op.alter_column("seats", "price", nullable=False)

    # Drop FK + index + column seat_type_id
    op.drop_constraint("seats_seat_type_id_fkey", "seats", type_="foreignkey")
    op.drop_index(op.f("ix_seats_seat_type_id"), table_name="seats")
    op.drop_column("seats", "seat_type_id")

    # Drop bảng seat_types
    op.drop_index("uq_seat_type_room_name", table_name="seat_types")
    op.drop_index(op.f("ix_seat_types_room_id"), table_name="seat_types")
    op.drop_table("seat_types")
