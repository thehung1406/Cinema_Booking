import httpx
import pytest
from fastapi.testclient import TestClient
from gateway.app.config import GatewaySettings
from gateway.app.main import create_app


def config(cinema=False):
    return GatewaySettings(_env_file=None, monolith_url="http://legacy",
        upstreams={"catalog": "http://catalog", **({"cinema":"http://cinema"} if cinema else {})}, enabled_domains=["catalog"]+(["cinema"] if cinema else []))


@pytest.mark.parametrize("cinema",[False,True])
def test_admin_references_composed_from_owners_and_same_auth_forwarded(cinema):
    received = []
    def upstream(request):
        assert request.url.path == "/admin/catalog"
        received.append((request.url.host, dict(request.headers)))
        if request.url.host == ("cinema" if cinema else "legacy"):
            return httpx.Response(200, json={"rooms": [{"id": 1}], "theaters": [{"id": 2}], "films": ["stale"]})
        return httpx.Response(200, json={"films": [{"id": 3}], "genres": [{"id": 4}], "formats": [{"id": 5}]})
    with TestClient(create_app(config(cinema), transport=httpx.MockTransport(upstream))) as client:
        response = client.get("/api/admin/catalog", headers={"Authorization": "Bearer same-token", "X-User-ID": "999", "X-Service-Key": "untrusted"})
    assert response.status_code == 200
    assert response.json() == {"rooms": [{"id": 1}], "theaters": [{"id": 2}], "films": [{"id": 3}], "genres": [{"id": 4}], "formats": [{"id": 5}]}
    assert len(received) == 2
    for _, headers in received:
        assert headers["authorization"] == "Bearer same-token"
        assert "x-user-id" not in headers and "x-service-key" not in headers


@pytest.mark.parametrize("failure,status", [("outage", 503), ("malformed", 503), ("denied", 403)])
def test_admin_aggregation_has_no_partial_or_unauthorized_success(failure, status):
    def upstream(request):
        if request.url.host == "legacy":
            return httpx.Response(200, json={"rooms": [], "theaters": []})
        if failure == "outage": raise httpx.ConnectError("Catalog unavailable")
        if failure == "denied": return httpx.Response(403)
        return httpx.Response(200, json={"films": []})
    with TestClient(create_app(config(), transport=httpx.MockTransport(upstream))) as client:
        response = client.get("/api/admin/catalog")
        assert response.status_code == status
        assert "rooms" not in response.json()
