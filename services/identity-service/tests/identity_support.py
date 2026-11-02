import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from identity_service.config import Settings
from identity_service.main import create_app
from identity_service.models import Base, Role, Permission, RolePermission, User
from identity_service.tokens import passwords


@pytest.fixture
def identity_store():
    url = os.environ.get("IDENTITY_DATABASE_URL", "")
    if "test" not in url:
        pytest.skip("Dedicated Identity test DB required")
    root = create_engine(url)
    schema = "identity_test_" + uuid4().hex
    with root.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with root.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()


@pytest.fixture
def identity_settings():
    return Settings(writes_enabled=True, current_kid="test-key",
        signing_keys={"test-key": "isolated-signing-key-32-characters-test-only"})


@pytest.fixture
def identity_client(identity_store, identity_settings):
    with Session(identity_store) as db:
        db.add_all([Role(id=1, code="USER", name="User"), Role(id=2, code="ADMIN", name="Admin"),
                    Role(id=3, code="STAFF", name="Staff")])
        codes = ["users.manage", "roles.manage", "reviews.moderate", "tickets.check_in", "films.manage"]
        db.add_all([Permission(id=i, code=code, name=code) for i, code in enumerate(codes, 1)])
        db.flush()
        db.add_all([RolePermission(role_id=2, permission_id=i) for i in range(1, len(codes)+1)])
        db.add(User(username="admin", email="admin@example.com", full_name="Admin", role_id=2,
                    password=passwords.hash("Strong-test-password")))
        db.commit()
    with TestClient(create_app(identity_settings, engine=identity_store)) as client:
        yield client


def register(client, name="customer"):
    response = client.post("/auth/register", json=dict(username=name, password="Strong-test-password",
        email=name+"@example.com", full_name="Customer", phone=None))
    assert response.status_code == 200, response.text
    return response.json()


def login(client, name="customer"):
    response = client.post("/auth/login", data={"username": name, "password": "Strong-test-password"})
    assert response.status_code == 200, response.text
    return response.json()


def bearer(pair):
    return {"Authorization": "Bearer " + pair["access_token"]}
