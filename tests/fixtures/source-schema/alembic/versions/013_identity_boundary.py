"""Identity extraction fence and external user references; preserve booking contact history."""
from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("INSERT INTO domain_ownership(domain,owner,updated_at) VALUES ('identity','monolith',CURRENT_TIMESTAMP)")
    for name, size in (("customer_full_name", 100), ("customer_email", 100), ("customer_phone", 15)):
        op.add_column("bookings", sa.Column(name, sa.String(size)))
    op.execute("""UPDATE bookings b SET customer_full_name=u.full_name, customer_email=u.email,
        customer_phone=u.phone FROM users u WHERE u.id=b.user_id""")
    # Includes read-only AI/Review archives: no cross-domain cascade into histories.
    inspector = sa.inspect(op.get_bind())
    for table in ("bookings", "seat_status", "ai_conversations", "reviews"):
        for fk in inspector.get_foreign_keys(table):
            if fk["referred_table"] == "users":
                op.drop_constraint(fk["name"], table, type_="foreignkey")
    op.execute("""CREATE FUNCTION identity_legacy_write_guard() RETURNS trigger AS $$
        DECLARE owner_state text;
        BEGIN
            SELECT owner INTO owner_state FROM domain_ownership WHERE domain='identity' FOR SHARE;
            IF owner_state IS DISTINCT FROM 'monolith' THEN
                RAISE EXCEPTION 'Identity legacy writer is frozen or transferred';
            END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql""")
    for table in ("users", "roles", "permissions", "role_permissions"):
        op.execute(f"CREATE TRIGGER identity_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION identity_legacy_write_guard()")


def downgrade():
    owner = op.get_bind().execute(sa.text("SELECT owner FROM domain_ownership WHERE domain='identity'")).scalar()
    if owner != "monolith":
        raise RuntimeError("Identity extraction requires reconciliation before downgrade")
    for table in ("users", "roles", "permissions", "role_permissions"):
        op.execute(f"DROP TRIGGER identity_owner_guard ON {table}")
    op.execute("DROP FUNCTION identity_legacy_write_guard()")
    for table, column, ondelete in (("bookings", "user_id", "RESTRICT"), ("seat_status", "hold_by_user_id", "SET NULL"),
                                  ("ai_conversations", "user_id", "CASCADE"), ("reviews", "user_id", None)):
        op.create_foreign_key(f"{table}_{column}_fkey", table, "users", [column], ["id"], ondelete=ondelete)
    for name in ("customer_full_name", "customer_email", "customer_phone"):
        op.drop_column("bookings", name)
    op.execute("DELETE FROM domain_ownership WHERE domain='identity'")
