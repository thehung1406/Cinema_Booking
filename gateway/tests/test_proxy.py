"""HTTP behavior at the migration boundary, without external services."""

from contextlib import contextmanager
import gzip
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse, RedirectResponse, Response

from gateway.app.config import GatewaySettings
from gateway.app.main import create_app


@contextmanager
def gateway_client(upstream):
    transport = httpx.ASGITransport(app=upstream) if isinstance(upstream, FastAPI) else upstream
    settings = GatewaySettings(monolith_url="http://monolith:8000", _env_file=None)
    with TestClient(create_app(settings, transport=transport), follow_redirects=False) as client:
        yield client


@pytest.fixture
def upstream():
    app = FastAPI()

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
    async def echo(request: Request):
        return JSONResponse({
            "method": request.method,
            "path": request.scope["raw_path"].decode("ascii"),
            "query": request.scope["query_string"].decode("ascii"),
            "body": (await request.body()).decode("utf-8"),
            "headers": dict(request.headers),
        })

    return app


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def test_method_body_and_bearer_token_reach_upstream(upstream, method):
    with gateway_client(upstream) as client:
        result = client.request(method, "/api/bookings", content=b'{"seats":[1,2]}', headers={"Authorization": "Bearer example", "Content-Type": "application/json"})
    assert result.status_code == 200
    data = result.json()
    assert data["method"] == method
    assert data["body"] == '{"seats":[1,2]}'
    assert data["headers"]["authorization"] == "Bearer example"
    assert data["headers"]["host"] == "monolith:8000"


def test_signed_query_is_byte_preserved_and_not_retried(upstream):
    query = "vnp_OrderInfo=Ve+phim%2Bcombo&vnp_Amount=25000000&x=1&x=2&vnp_SecureHash=a%2fb%2Fc"
    with gateway_client(upstream) as client:
        result = client.get("/api/payment/vnpay-ipn?" + query)
    assert result.json()["query"] == query


def test_encoded_path_is_not_decoded_and_reencoded(upstream):
    with gateway_client(upstream) as client:
        result = client.get("/api/films/a%2Fb")
    assert result.json()["path"] == "/films/a%2Fb"


@pytest.mark.parametrize("path,expected", [("/api", "/"), ("/api/", "/"), ("/api/films/", "/films/")])
def test_root_and_trailing_slash_preserved(upstream, path, expected):
    with gateway_client(upstream) as client:
        result = client.get(path)
    assert result.json()["path"] == expected


def test_client_cannot_spoof_identity_or_forwarded_context(upstream):
    headers = {
        "X-User-ID": "1", "X-Role": "ADMIN", "X-Permissions": "all",
        "X-Auth-User": "1", "X-Internal-Token": "secret", "X-Service-Key": "secret",
        "Forwarded": "host=evil.example", "X-Forwarded-For": "127.0.0.1",
        "X-Request-ID": "fake", "Connection": "X-Drop-Me", "X-Drop-Me": "secret",
    }
    with gateway_client(upstream) as client:
        result = client.get("/api/auth/me", headers=headers)
    forwarded = result.json()["headers"]
    for key in headers:
        if key != "X-Request-ID":
            assert key.lower() not in forwarded
    UUID(forwarded["x-request-id"])
    assert forwarded["x-request-id"] == result.headers["x-request-id"]
    assert forwarded["x-request-id"] != "fake"


@pytest.mark.parametrize("status", [201, 204, 400, 401, 403, 404, 409, 422, 500])
def test_status_and_error_body_unchanged(status):
    app = FastAPI()

    @app.get("/result")
    async def result():
        return Response(b"" if status == 204 else b'{"detail":"original"}', status_code=status, media_type="application/json")

    with gateway_client(app) as client:
        response = client.get("/api/result")
    assert response.status_code == status
    assert response.content == (b"" if status == 204 else b'{"detail":"original"}')


def test_gzip_and_multiple_set_cookie_headers_survive_without_cookie_leak():
    app = FastAPI()
    compressed = gzip.compress(b'{"ok":true}')

    @app.get("/cookies")
    async def cookies():
        response = Response(compressed, headers={"Content-Encoding": "gzip", "Content-Type": "application/json"})
        response.set_cookie("one", "private")
        response.set_cookie("two", "private")
        return response

    @app.get("/echo")
    async def echo(request: Request):
        return {"cookie": request.headers.get("cookie")}

    with gateway_client(app) as client:
        result = client.get("/api/cookies")
        assert result.json() == {"ok": True}
        assert result.headers["content-length"] == str(len(compressed))
        assert len(result.headers.get_list("set-cookie")) == 2
        # A different browser must not inherit the gateway AsyncClient cookie jar.
        client.cookies.clear()
        assert client.get("/api/echo").json()["cookie"] is None


@pytest.mark.parametrize("location,expected", [
    ("http://monolith:8000/films/?x=1%2B2", "/api/films/?x=1%2B2"),
    ("/films/", "/api/films/"),
    ("https://sandbox.vnpayment.vn/payment?x=1", "https://sandbox.vnpayment.vn/payment?x=1"),
])
def test_redirect_does_not_leak_internal_origin_or_follow_external_url(location, expected):
    app = FastAPI()

    @app.get("/redirect")
    async def redirect():
        return RedirectResponse(location, status_code=307)

    with gateway_client(app) as client:
        response = client.get("/api/redirect")
    assert response.status_code == 307
    assert response.headers["location"] == expected


@pytest.mark.parametrize("exception,status", [(httpx.ConnectError, 502), (httpx.ReadTimeout, 504)])
def test_upstream_failure_does_not_retry_a_booking_write(exception, status):
    calls = []

    def handler(request):
        calls.append(request)
        raise exception("do not expose internal connection information", request=request)

    with gateway_client(httpx.MockTransport(handler)) as client:
        response = client.post("/api/bookings", json={"seats": [1]})
        ready = client.get("/health/ready")
        live = client.get("/health/live")
    assert response.status_code == status
    assert len([r for r in calls if r.method == "POST"]) == 1
    assert "internal connection" not in response.text
    assert ready.status_code == 503
    assert live.status_code == 200
    UUID(response.headers["x-request-id"])


def test_health_and_unknown_paths(upstream):
    with gateway_client(upstream) as client:
        assert client.get("/health/ready").status_code == 200
        assert client.get("/health/live").status_code == 200
        assert client.get("/auth/me").status_code == 404
        assert client.get("/apix/auth/me").status_code == 404


def test_network_path_cannot_change_upstream_host(upstream):
    with gateway_client(upstream) as client:
        result = client.get("/api//evil.example/payment")
    assert result.json()["headers"]["host"] == "monolith:8000"


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://user:secret@localhost", "http://localhost/base", "http://localhost?x=1", "http://localhost/#fragment"])
def test_upstream_config_rejects_non_origin_urls(url):
    with pytest.raises(ValueError):
        GatewaySettings(monolith_url=url, _env_file=None)


@pytest.mark.parametrize("path", ["/api/internal/v1/auth/introspect", "/api/%69nternal/v1/auth/introspect", "/api//internal/v1/auth/introspect"])
def test_internal_apis_are_not_exposed_by_the_public_gateway(upstream, path):
    with gateway_client(upstream) as client:
        assert client.post(path, json={"token": "not-public"}, headers={"X-Service-Key": "fake"}).status_code == 404
