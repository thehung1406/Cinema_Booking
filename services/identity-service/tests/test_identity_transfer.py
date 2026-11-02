import os
from uuid import uuid4
import pytest
from sqlalchemy import MetaData, Table, create_engine, text, select
from sqlalchemy.orm import Session
from identity_service.models import User
from identity_service.migrate import TABLES, transfer
from identity_service.tokens import passwords


def test_copy_actual_legacy_accounts_rbac_hashes_timestamps_and_sequences(identity_store):
    root = create_engine(os.environ["TEST_POSTGRES_URL"])
    schema = "identity_copy_test_" + uuid4().hex
    with root.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    source = create_engine(os.environ["TEST_POSTGRES_URL"], connect_args={"options": f"-csearch_path={schema}"})
    try:
        metadata = MetaData()
        for name in TABLES:
            Table(name, metadata, autoload_with=root)
        metadata.create_all(source)
        hashed = passwords.hash("Existing-password-123")
        with source.begin() as conn:
            conn.execute(text("INSERT INTO roles(id,code,name) VALUES (41,'USER','User')"))
            conn.execute(text("INSERT INTO permissions(id,code,name) VALUES (52,'films.manage','Films')"))
            conn.execute(text("INSERT INTO role_permissions VALUES (41,52)"))
            conn.execute(text("""INSERT INTO users(id,username,password,email,phone,full_name,avatar,role_id,is_active,created_at)
                VALUES (99,'existing',:password,'existing@example.com',NULL,'Người dùng','avatar',41,false,'2024-01-02T03:04:05Z')"""), {"password": hashed})
            for name in ("users", "roles", "permissions"):
                conn.execute(text("SELECT setval(pg_get_serial_sequence(:name,'id'),100000,true)"), {"name": name})
        with pytest.raises(ValueError):
            transfer(source, identity_store, apply=True)
        with pytest.raises(ValueError):
            transfer(source, identity_store)
        result = transfer(source, identity_store, apply=True, frozen=True)
        assert result["verified"] and result["tables"]["users"]["rows"] == 1
        assert not transfer(source, identity_store, apply=True, frozen=True)["copied"]
        assert transfer(source, identity_store)["verified"]
        with Session(identity_store) as db:
            user = db.get(User, 99)
            assert user.password == hashed and passwords.verify("Existing-password-123", user.password)
            assert not user.is_active and user.full_name == "Người dùng" and user.role == "USER"
            assert user.created_at.isoformat() == "2024-01-02T03:04:05+00:00"
            fresh = User(username="new", email="new@example.com", password=hashed, role_id=41)
            db.add(fresh)
            db.commit()
            assert fresh.id > 100000
        with pytest.raises(ValueError):
            transfer(source, identity_store, apply=True, frozen=True)
    finally:
        source.dispose()
        with root.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()
