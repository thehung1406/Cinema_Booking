import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from identity_service.bootstrap import initialize, PERMISSIONS
from identity_service.models import Permission, Role, RolePermission, User
from identity_service.main import create_app
from identity_service.tokens import passwords

BODY = dict(
    username="first-admin",
    email="admin@example.com",
    full_name="First Admin",
    password="Strong-bootstrap-test-password",
)


def test_fresh_bootstrap_login_rbac_and_register_without_legacy(
    identity_store, identity_settings
):
    initialize(identity_store, BODY)
    with Session(identity_store) as db:
        user = db.scalar(select(User))
        assert user.role == "ADMIN" and passwords.verify(
            BODY["password"], user.password
        )
        assert (
            set(
                db.scalars(
                    select(Permission.code)
                    .join(RolePermission)
                    .where(RolePermission.role_id == user.role_id)
                )
            )
            == PERMISSIONS
        )
        original_hash = user.password
    with TestClient(create_app(identity_settings, engine=identity_store)) as client:
        pair = client.post(
            "/auth/login",
            data={"username": BODY["username"], "password": BODY["password"]},
        )
        assert pair.status_code == 200
        assert (
            client.get(
                "/access-control/permissions",
                headers={"Authorization": "Bearer " + pair.json()["access_token"]},
            ).status_code
            == 200
        )
        customer = client.post(
            "/auth/register",
            json={
                **BODY,
                "username": "first-customer",
                "email": "customer@example.com",
            },
        )
        assert customer.status_code == 200
    with pytest.raises(RuntimeError, match="not empty"):
        initialize(
            identity_store, {**BODY, "password": "Never-overwrite-this-password"}
        )
    with Session(identity_store) as db:
        assert (
            db.scalar(select(User).where(User.username == BODY["username"])).password
            == original_hash
        )


def test_bootstrap_invalid_secret_never_appears_in_error_or_partial_rbac(
    identity_store,
):
    secret = "short"
    with pytest.raises(ValueError) as caught:
        initialize(identity_store, {**BODY, "password": secret})
    assert secret not in str(caught.value)
    with Session(identity_store) as db:
        assert db.scalar(select(func.count()).select_from(Role)) == 0
