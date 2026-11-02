"""Frozen technical capture schema. Business export views live in owner migrations."""


def install(op, source, view_sql, triggers):
    op.execute(
        """
    CREATE TABLE report_source_state (id integer PRIMARY KEY CHECK(id=1),generation uuid NOT NULL,checkpoint bigint NOT NULL DEFAULT 0);
    INSERT INTO report_source_state(id,generation) VALUES (1,gen_random_uuid());
    CREATE TABLE report_dirty (kind text NOT NULL,key text NOT NULL,version bigint NOT NULL DEFAULT 1,
      changed_at timestamptz NOT NULL DEFAULT clock_timestamp(),PRIMARY KEY(kind,key));
    CREATE TABLE report_source_facts (kind text NOT NULL,key text NOT NULL,version bigint NOT NULL,
      changed_at timestamptz NOT NULL,deleted boolean NOT NULL,payload jsonb NOT NULL,PRIMARY KEY(kind,key));
    CREATE TABLE report_snapshots (id uuid PRIMARY KEY,generation uuid NOT NULL,created_at timestamptz NOT NULL,
      row_count bigint NOT NULL,sha256 text NOT NULL);
    CREATE TABLE report_snapshot_rows (snapshot_id uuid REFERENCES report_snapshots(id) ON DELETE CASCADE,
      ordinal bigint NOT NULL,fact jsonb NOT NULL,PRIMARY KEY(snapshot_id,ordinal));
    CREATE FUNCTION report_touch(p_kind text,p_key text) RETURNS void LANGUAGE sql AS $$
      INSERT INTO report_dirty(kind,key) SELECT p_kind,p_key WHERE p_key IS NOT NULL
      ON CONFLICT(kind,key) DO UPDATE SET version=report_dirty.version+1,changed_at=clock_timestamp();
    $$;
    """
    )
    op.execute("CREATE VIEW reporting_export AS " + view_sql)
    for table, body in triggers.items():
        # All identifiers/bodies are frozen literals in a reviewed owner migration.
        op.execute(
            f"""CREATE FUNCTION report_touch_{table}() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN {body} RETURN COALESCE(NEW,OLD); END $$;
          CREATE TRIGGER reporting_dirty AFTER INSERT OR UPDATE OR DELETE ON {table}
          FOR EACH ROW EXECUTE FUNCTION report_touch_{table}();"""
        )
    op.execute(
        "INSERT INTO report_dirty(kind,key) SELECT kind,key FROM reporting_export ON CONFLICT DO NOTHING"
    )


def touch(kind, expression):
    return f"PERFORM report_touch('{kind}',({expression})::text);"
