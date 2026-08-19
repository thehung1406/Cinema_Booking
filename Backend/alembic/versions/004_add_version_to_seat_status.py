"""Add version column to seat_status for optimistic locking

Revision ID: 004
Revises: 003
Create Date: 2026-08-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, Sequence[str], None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Thêm cột version vào bảng seat_status phục vụ Optimistic Locking."""
    op.add_column(
        "seat_status",
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Xóa cột version khỏi bảng seat_status."""
    op.drop_column("seat_status", "version")
