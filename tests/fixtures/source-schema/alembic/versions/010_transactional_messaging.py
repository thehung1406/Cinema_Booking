"""Local messaging state and permission for audited notification operations.

Revision ID: 010
Revises: 009
"""
from alembic import op
from cinema_platform import migrations_v1

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    migrations_v1.create(op)
    op.execute("INSERT INTO permissions(code,name) VALUES ('notifications.manage','Quản lý gửi thông báo') ON CONFLICT (code) DO NOTHING")
    op.execute("""INSERT INTO role_permissions(role_id,permission_id)
        SELECT r.id,p.id FROM roles r CROSS JOIN permissions p
        WHERE r.code='ADMIN' AND p.code='notifications.manage' ON CONFLICT DO NOTHING""")


def downgrade():
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code='notifications.manage')")
    op.execute("DELETE FROM permissions WHERE code='notifications.manage'")
    migrations_v1.drop(op)
