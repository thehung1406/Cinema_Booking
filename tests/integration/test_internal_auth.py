from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlmodel import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend/tests"))
from test_normalized_schema import pg, catalog  # noqa: E402,F401
from main import app  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import get_session  # noqa: E402
from app.models import Permission, RolePermission  # noqa: E402
from app.utils.dependencies import redis_client  # noqa: E402
from app.utils.security import create_access_token, create_refresh_token  # noqa: E402


def test_internal_identity_requires_service_credential_and_rechecks_revocation_active_and_permissions(pg, catalog, monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_KEY", "isolated-internal-service-key-for-tests-only")
    revoked = set()
    monkeypatch.setattr(redis_client, "get", lambda key: "revoked" if key in revoked else None)
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = lambda: pg
    token = create_access_token({"sub": str(catalog["user"].id), "role": "ADMIN"})
    headers = {"X-Service-Key": settings.INTERNAL_SERVICE_KEY}
    path = "/internal/v1/auth/introspect"
    try:
        with TestClient(app) as client:
            assert client.post(path, json={"token": token}).status_code == 401
            response = client.post(path, headers=headers, json={"token": token})
            assert response.status_code == 200
            assert set(response.json()) == {"user_id", "role", "permissions", "is_active"}
            assert response.json()["role"] == "USER"  # signed role claim cannot elevate DB role
            permission = pg.exec(select(Permission).where(Permission.code == "notifications.manage")).one()
            grant = RolePermission(role_id=catalog["user"].role_id, permission_id=permission.id)
            pg.add(grant)
            pg.flush()
            assert "notifications.manage" in client.post(path, headers=headers, json={"token": token}).json()["permissions"]
            pg.delete(grant)
            pg.flush()
            assert "notifications.manage" not in client.post(path, headers=headers, json={"token": token}).json()["permissions"]
            revoked.add("blacklist:" + token)
            assert client.post(path, headers=headers, json={"token": token}).status_code == 401
            revoked.clear()
            refresh = create_refresh_token({"sub": str(catalog["user"].id)})
            assert client.post(path, headers=headers, json={"token": refresh}).status_code == 401
            catalog["user"].is_active = False
            pg.flush()
            assert client.post(path, headers=headers, json={"token": token}).status_code == 403
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)
