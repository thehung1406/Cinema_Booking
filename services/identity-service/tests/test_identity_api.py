from datetime import timedelta
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from identity_service.main import create_app
from identity_service.models import User, LoginSession, utcnow
from identity_service.tokens import mint
from identity_support import register, login, bearer


def test_register_login_public_payload_cannot_choose_role_or_leak_hash(identity_client, identity_store):
    user = register(identity_client)
    assert user["role"] == "USER" and "password" not in user
    bad = dict(username="escalate", password="Strong-test-password", email="bad@example.com",
               full_name="Bad", role_id=2, is_active=True)
    assert identity_client.post("/auth/register", json=bad).status_code == 422
    assert identity_client.post("/auth/register", json={**bad, "role_id": None}).status_code == 422
    pair = login(identity_client)
    assert identity_client.get("/auth/me", headers=bearer(pair)).json()["id"] == user["id"]
    assert identity_client.get("/admin/employees", headers=bearer(pair)).status_code == 403
    with Session(identity_store) as db:
        row = db.get(User, user["id"])
        assert row.password != "Strong-test-password"
        session = db.scalar(select(LoginSession))
        assert session.refresh_digest != pair["refresh_token"]


def test_logout_revokes_access_and_refresh_immediately(identity_client, identity_settings):
    register(identity_client)
    pair = login(identity_client)
    refreshed = identity_client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert refreshed.status_code == 200
    other_access = refreshed.json()["access_token"]
    assert identity_client.post("/auth/logout", headers=bearer(pair)).status_code == 200
    assert identity_client.get("/auth/me", headers=bearer(pair)).status_code == 401
    assert identity_client.get("/auth/me", headers={"Authorization": "Bearer " + other_access}).status_code == 401
    assert identity_client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]}).status_code == 401


def test_dynamic_grants_role_lock_and_unlock_do_not_trust_old_claims(identity_client, identity_settings):
    user = register(identity_client)
    pair = login(identity_client)
    admin = bearer(login(identity_client, "admin"))
    private = {"X-Service-Key": identity_settings.service_key}
    def introspect():
        return identity_client.post("/internal/v1/auth/introspect", headers=private, json={"token": pair["access_token"]})
    assert introspect().json()["permissions"] == []
    assert identity_client.put(f'/access-control/users/{user["id"]}/role', headers=admin, json={"role_id": 3}).status_code == 200
    assert introspect().json()["role"] == "STAFF"
    assert identity_client.put('/access-control/roles/3/permissions', headers=admin, json={"permission_ids": [3, 4]}).status_code == 200
    assert introspect().json()["permissions"] == ["reviews.moderate", "tickets.check_in"]
    assert identity_client.put('/access-control/roles/3/permissions', headers=admin, json={"permission_ids": []}).status_code == 200
    assert introspect().json()["permissions"] == []
    assert identity_client.put(f'/admin/employees/{user["id"]}/status', headers=admin, json={"is_active": False}).status_code == 200
    assert introspect().status_code == 401  # session was also revoked
    assert identity_client.post('/auth/login', data={"username": "customer", "password": "Strong-test-password"}).status_code == 401
    assert identity_client.put(f'/admin/employees/{user["id"]}/status', headers=admin, json={"is_active": True}).status_code == 200
    assert introspect().status_code == 401
    login(identity_client)
    assert identity_client.put('/access-control/roles/2/permissions', headers=admin, json={"permission_ids": []}).status_code == 409
    assert identity_client.put('/access-control/users/1/role', headers=admin, json={"role_id": 1}).status_code == 409
    assert identity_client.put('/admin/employees/1/status', headers=admin, json={"is_active": False}).status_code == 409


@pytest.mark.parametrize("mutation", ["expired", "wrong-key", "wrong-issuer", "wrong-audience", "wrong-type", "no-session", "forged-role", "no-exp", "no-kid", "none-alg"])
def test_invalid_tokens_and_role_escalation(identity_client, identity_settings, mutation):
    user = register(identity_client)
    pair = login(identity_client)
    token = pair["access_token"]
    claims = jwt.get_unverified_claims(token)
    key = identity_settings.signing_keys[identity_settings.current_kid]
    headers = {"kid": identity_settings.current_kid}
    algorithm = "HS256"
    if mutation == "expired": claims["exp"] = int((utcnow()-timedelta(minutes=1)).timestamp())
    if mutation == "wrong-key": key = "forged-key-32-characters-for-tests-only"
    if mutation == "wrong-issuer": claims["iss"] = "attacker"
    if mutation == "wrong-audience": claims["aud"] = "different-api"
    if mutation == "wrong-type": token = pair["refresh_token"]
    if mutation == "no-session": claims["sid"] = str(uuid4())
    if mutation == "forged-role": claims["role"] = "ADMIN"
    if mutation == "no-exp": claims.pop("exp")
    if mutation == "no-kid": headers = {}
    if mutation == "none-alg":
        import base64, json
        enc = lambda data: base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()
        token = enc({"alg": "none", "kid": identity_settings.current_kid}) + "." + enc(claims) + "."
    elif mutation != "wrong-type":
        token = jwt.encode(claims, key, algorithm=algorithm, headers=headers)
    response = identity_client.get("/auth/me", headers={"Authorization": "Bearer " + token})
    if mutation == "forged-role":
        assert response.status_code == 200 and response.json()["role"] == "USER"
        assert identity_client.get("/admin/session", headers={"Authorization": "Bearer " + token}).status_code == 403
    else:
        assert response.status_code == 401


def test_key_rotation_overlap_then_retirement(identity_client, identity_settings):
    register(identity_client)
    old = login(identity_client)
    identity_settings.signing_keys["next-key"] = "next-isolated-signing-key-at-least-32-bytes"
    identity_settings.current_kid = "next-key"
    new = login(identity_client)
    assert jwt.get_unverified_header(new["access_token"])["kid"] == "next-key"
    assert identity_client.get("/auth/me", headers=bearer(old)).status_code == 200
    del identity_settings.signing_keys["test-key"]
    assert identity_client.get("/auth/me", headers=bearer(old)).status_code == 401
    assert identity_client.post("/auth/refresh", json={"refresh_token": old["refresh_token"]}).status_code == 401
    assert identity_client.get("/auth/me", headers=bearer(new)).status_code == 200


def test_private_credentials_profile_allowlist_and_freeze(identity_client, identity_settings):
    user = register(identity_client)
    pair = login(identity_client)
    path = "/internal/v1/auth/introspect"
    assert identity_client.post(path, json={"token": pair["access_token"]}).status_code == 401
    headers = {"X-Service-Key": identity_settings.service_key}
    response = identity_client.post(path, headers=headers, json={"token": pair["access_token"]})
    assert set(response.json()) == {"user_id", "role", "permissions", "is_active"}
    profiles = identity_client.post("/internal/v1/users/profiles", headers=headers, json={"user_ids": [user["id"]]}).json()
    assert set(profiles[0]) == {"id", "username", "email", "full_name", "phone", "role"}
    identity_settings.writes_enabled = False
    assert identity_client.post("/auth/logout", headers=bearer(pair)).status_code == 503
    assert identity_client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]}).status_code == 503
    assert identity_client.get("/auth/me", headers=bearer(pair)).status_code == 200


def test_session_deadline_and_legacy_jwt_rejected(identity_client, identity_store, identity_settings):
    register(identity_client)
    pair = login(identity_client)
    with Session(identity_store) as db:
        session = db.scalar(select(LoginSession))
        session.expires_at = utcnow()-timedelta(seconds=1)
        db.commit()
    assert identity_client.get("/auth/me", headers=bearer(pair)).status_code == 401
    legacy = jwt.encode(dict(sub="1", type="access", exp=utcnow()+timedelta(minutes=15)),
        identity_settings.signing_keys["test-key"], algorithm="HS256")
    assert identity_client.get("/auth/me", headers={"Authorization": "Bearer " + legacy}).status_code == 401
