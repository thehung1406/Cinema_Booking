"""UC01–UC07 permissions and account locking.

Revision ID: 009
Revises: 008
"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None

PERMISSIONS = [
    ("films.manage", "Quản lý phim"),
    ("rooms.manage", "Quản lý phòng và ghế"),
    ("showtimes.manage", "Quản lý lịch chiếu"),
    ("knowledge.manage", "Quản lý tài liệu chatbot"),
    ("reports.view", "Xem báo cáo thống kê"),
]


def upgrade():
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    for code, name in PERMISSIONS:
        op.execute(sa.text("INSERT INTO permissions(code,name) VALUES (:code,:name) ON CONFLICT (code) DO NOTHING")
            .bindparams(sa.bindparam("code", code), sa.bindparam("name", name)))
    op.execute("""
        INSERT INTO role_permissions(role_id,permission_id)
        SELECT r.id,p.id FROM roles r CROSS JOIN permissions p
        WHERE r.code='ADMIN' OR (r.code='MANAGER' AND p.code IN
          ('films.manage','rooms.manage','showtimes.manage','seat_types.manage'))
        ON CONFLICT DO NOTHING
    """)


def downgrade():
    for code, _ in PERMISSIONS:
        op.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code=:code)")
            .bindparams(sa.bindparam("code", code)))
        op.execute(sa.text("DELETE FROM permissions WHERE code=:code").bindparams(sa.bindparam("code", code)))
    op.drop_column("users", "is_active")
