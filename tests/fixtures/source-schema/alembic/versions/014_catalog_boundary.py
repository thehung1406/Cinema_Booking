"""Catalog ownership, historical facts and external references."""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None

TABLES = ("films", "genres", "formats", "film_genres", "film_formats", "food_items", "combo_items")


def upgrade():
    op.execute("INSERT INTO domain_ownership(domain,owner,updated_at) VALUES ('catalog','monolith',CURRENT_TIMESTAMP)")
    for table in ("films", "food_items"):
        op.add_column(table, sa.Column("catalog_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("showtimes", sa.Column("catalog_binding_id", sa.String(36)))
    for table in ("showtimes", "bookings"):
        op.add_column(table, sa.Column("catalog_film_snapshot", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("bookings", sa.Column("food_quote_id", sa.String(36)))
    op.add_column("bookings", sa.Column("food_quote_version", sa.Integer()))
    op.add_column("bookings", sa.Column("food_quote_expires_at", sa.DateTime(timezone=True)))
    op.execute("""UPDATE showtimes s SET catalog_binding_id=md5('catalog-showtime:'||s.id::text)::uuid::text,
        catalog_film_snapshot=(to_jsonb(f) || jsonb_build_object(
            'format_name',fmt.name, 'duration',f.duration_minutes::text||' phút',
            'genre',(SELECT string_agg(g.name,', ' ORDER BY g.id) FROM genres g JOIN film_genres fg ON fg.genre_id=g.id WHERE fg.film_id=f.id),
            'formats',(SELECT coalesce(jsonb_agg(ffmt.name ORDER BY ffmt.id),'[]') FROM formats ffmt JOIN film_formats ff ON ff.format_id=ffmt.id WHERE ff.film_id=f.id),
            'genre_ids',(SELECT coalesce(jsonb_agg(fg.genre_id ORDER BY fg.genre_id),'[]') FROM film_genres fg WHERE fg.film_id=f.id),
            'format_ids',(SELECT coalesce(jsonb_agg(ff.format_id ORDER BY ff.format_id),'[]') FROM film_formats ff WHERE ff.film_id=f.id)))::json
        FROM films f, formats fmt WHERE f.id=s.film_id AND fmt.id=s.format_id""")
    op.execute("UPDATE bookings b SET catalog_film_snapshot=s.catalog_film_snapshot FROM showtimes s WHERE s.id=b.showtime_id")
    inspector = sa.inspect(op.get_bind())
    for table in ("showtimes", "reviews", "booking_food_items"):
        for fk in inspector.get_foreign_keys(table):
            if fk["referred_table"] in {"films", "formats", "film_formats", "food_items"}:
                op.drop_constraint(fk["name"], table, type_="foreignkey")
    op.execute("""CREATE FUNCTION catalog_legacy_write_guard() RETURNS trigger AS $$
        DECLARE state text;
        BEGIN
            SELECT owner INTO state FROM domain_ownership WHERE domain='catalog' FOR SHARE;
            IF state IS DISTINCT FROM 'monolith' THEN RAISE EXCEPTION 'Catalog legacy writer is frozen or transferred'; END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql""")
    for table in TABLES:
        op.execute(f"CREATE TRIGGER catalog_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION catalog_legacy_write_guard()")
    op.execute("""CREATE FUNCTION catalog_schedule_guard() RETURNS trigger AS $$
        DECLARE state text;
        BEGIN
            SELECT owner INTO state FROM domain_ownership WHERE domain='catalog' FOR SHARE;
            IF state='maintenance' THEN RAISE EXCEPTION 'Catalog schedules are frozen'; END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            IF state='service' THEN
                IF NEW.catalog_binding_id IS NULL OR NEW.catalog_film_snapshot->>'id' IS DISTINCT FROM NEW.film_id::text THEN
                    RAISE EXCEPTION 'Catalog schedule binding/snapshot required';
                END IF;
                IF TG_OP='UPDATE' AND (NEW.film_id,NEW.format_id,NEW.show_date,NEW.start_time,NEW.end_time)
                    IS DISTINCT FROM (OLD.film_id,OLD.format_id,OLD.show_date,OLD.start_time,OLD.end_time)
                    AND NEW.catalog_binding_id IS NOT DISTINCT FROM OLD.catalog_binding_id THEN
                    RAISE EXCEPTION 'Changed schedule requires a new Catalog binding';
                END IF;
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql""")
    op.execute("CREATE TRIGGER catalog_schedule_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON showtimes FOR EACH ROW EXECUTE FUNCTION catalog_schedule_guard()")


def downgrade():
    owner = op.get_bind().execute(sa.text("SELECT owner FROM domain_ownership WHERE domain='catalog'")).scalar()
    if owner != "monolith":
        raise RuntimeError("Catalog extraction requires reconciliation before downgrade")
    op.execute("DROP TRIGGER catalog_schedule_owner_guard ON showtimes")
    op.execute("DROP FUNCTION catalog_schedule_guard()")
    for table in TABLES:
        op.execute(f"DROP TRIGGER catalog_owner_guard ON {table}")
    op.execute("DROP FUNCTION catalog_legacy_write_guard()")
    for table, column, target in (("showtimes", "film_id", "films"), ("showtimes", "format_id", "formats"), ("reviews", "film_id", "films"), ("booking_food_items", "food_item_id", "food_items")):
        op.create_foreign_key(f"{table}_{column}_fkey", table, target, [column], ["id"], ondelete="RESTRICT" if table != "reviews" else None)
    op.create_foreign_key("fk_showtime_film_format", "showtimes", "film_formats", ["film_id", "format_id"], ["film_id", "format_id"], ondelete="RESTRICT")
    for table, columns in (("bookings", ["food_quote_id", "food_quote_version", "food_quote_expires_at", "catalog_film_snapshot"]),
                           ("showtimes", ["catalog_binding_id", "catalog_film_snapshot"]),
                           ("films", ["catalog_version"]), ("food_items", ["catalog_version"])):
        for column in columns:
            op.drop_column(table, column)
    op.execute("DELETE FROM domain_ownership WHERE domain='catalog'")
