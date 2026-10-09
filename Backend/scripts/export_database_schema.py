"""Export the final 23-table PostgreSQL schema, without legacy intermediate tables."""
import importlib.util
import sys
from pathlib import Path
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable, CreateIndex
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlmodel import SQLModel

backend = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend))
import app.models  # noqa: E402,F401 - register all tables


def export(path):
    dialect = postgresql.dialect()
    migration_path = backend / "alembic/versions/006_normalized_booking_schema.py"
    spec = importlib.util.spec_from_file_location("schema_006", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert len(SQLModel.metadata.tables) == 23
    with path.open("w", encoding="utf-8") as handle:
        handle.write("-- Cinema Booking schema 006: 23 application tables.\n")
        handle.write("-- FRESH DATABASE ONLY. Existing databases: python -m alembic upgrade head.\n\nBEGIN;\n")
        for table in SQLModel.metadata.sorted_tables:
            handle.write(str(CreateTable(table).compile(dialect=dialect)) + ";\n")
        for table in SQLModel.metadata.sorted_tables:
            for index in sorted(table.indexes, key=lambda item: item.name):
                handle.write(str(CreateIndex(index).compile(dialect=dialect)) + ";\n")
        handle.write("""
INSERT INTO roles(code,name) VALUES
 ('USER','USER'),('STAFF','STAFF'),('MANAGER','MANAGER'),('ADMIN','ADMIN');
INSERT INTO permissions(code,name) VALUES
 ('tickets.check_in','Kiểm vé'),('reviews.moderate','Duyệt đánh giá'),
 ('seat_types.manage','Quản lý giá và loại ghế'),
 ('users.manage','Gán vai trò người dùng'),('roles.manage','Quản lý phân quyền');
INSERT INTO role_permissions(role_id,permission_id)
 SELECT r.id,p.id FROM roles r CROSS JOIN permissions p
 WHERE r.code='ADMIN' OR (r.code IN ('STAFF','MANAGER')
       AND p.code IN ('tickets.check_in','reviews.moderate','seat_types.manage'));
""")
        context = MigrationContext.configure(dialect_name="postgresql",
            opts={"as_sql": True, "output_buffer": handle})
        with Operations.context(context):
            migration._install_integrity_triggers()
        handle.write("""
CREATE TABLE alembic_version (version_num varchar(32) NOT NULL PRIMARY KEY);
INSERT INTO alembic_version VALUES ('006');
COMMIT;
""")
    path.write_text("\n".join(line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()) + "\n",
                    encoding="utf-8")
    print(path.resolve())


if __name__ == "__main__":
    export(backend / "migrations/006_full_database.sql")
