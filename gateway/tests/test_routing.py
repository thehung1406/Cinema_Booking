import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from gateway.app.config import GatewaySettings
from gateway.app.main import create_app
from gateway.app.routing import owner


@pytest.mark.parametrize("path,domain", [
    ("/films/positive-trending", "review"), ("/films/1/reviews/mine", "review"),
    ("/films/1/sentiment-summary", "review"), ("/films/1", "catalog"),
    ("/admin/cinema-operations/abc", "cinema"), ("/admin/theaters", "cinema"),
    ("/admin/showtimes/1/sales/close", "cinema"), ("/admin/rooms/1/seats", "cinema"), ("/seats/showtime/1", "booking"),
    ("/payment/vnpay-ipn", "payment"), ("/admin/documents/1", "ai"),
    ("/admin/payment-reconciliation", "payment"), ("/admin/payment-reconciliation/case/retry", "payment"),
    ("/admin/employees", "identity"), ("/admin/reports", "reporting"),
    ("/admin/catalog", "legacy"), ("/authentic", "legacy"),
])
def test_domain_ownership_and_specific_film_route_priority(path, domain):
    assert owner(path) == domain


def test_configured_domain_switch_does_not_switch_unenabled_domains():
    upstream = FastAPI()
    @upstream.get("/{path:path}")
    def echo(request: Request):
        return {"host": request.headers["host"]}
    settings = GatewaySettings(_env_file=None, monolith_url="http://legacy:8000",
        upstreams={"review": "http://reviews:8001", "catalog": "http://catalog:8002"}, enabled_domains=["review"])
    with TestClient(create_app(settings, transport=httpx.ASGITransport(app=upstream))) as client:
        assert client.get("/api/films/1/reviews").json()["host"] == "reviews:8001"
        assert client.get("/api/films/1").json()["host"] == "legacy:8000"
        assert client.get("/api/admin/catalog").json()["host"] == "legacy:8000"


def test_enabling_missing_or_unknown_target_fails_startup():
    with pytest.raises(ValueError):
        GatewaySettings(_env_file=None, enabled_domains=["review"])
    with pytest.raises(ValueError):
        GatewaySettings(_env_file=None, upstreams={"fake": "http://example.test"})


@pytest.mark.parametrize("required,status", [([],200),(["ai"],503)])
@pytest.mark.parametrize("domain", ["ai", "review", "identity", "catalog", "cinema"])
def test_optional_domain_outage_does_not_remove_booking_gateway_readiness(required, status, domain):
    from fastapi.responses import JSONResponse
    upstream = FastAPI()
    @upstream.get("/")
    def root():
        return {"status": "ok"}
    @upstream.get("/health/ready")
    def health():
        return JSONResponse({"status": "not_ready"}, status_code=503)
    settings = GatewaySettings(_env_file=None, monolith_url="http://legacy",
        upstreams={domain:f"http://{domain}"}, enabled_domains=[domain], required_domains=[domain] if required else [])
    with TestClient(create_app(settings, transport=httpx.ASGITransport(app=upstream))) as client:
        assert client.get("/health/ready").status_code == status


def test_booking_and_temporary_payment_route_to_same_owner_preserving_checkout_key():
    received=[]
    upstream=FastAPI()
    @upstream.api_route("/{path:path}",methods=["GET","POST"])
    async def echo(request:Request):
        await request.body()
        received.append((request.url.hostname,request.url.path,request.headers.get('idempotency-key')))
        return {"service":"booking"}
    cfg=GatewaySettings(_env_file=None,monolith_url="http://legacy",upstreams={"booking":"http://booking:8087","payment":"http://booking:8087"},enabled_domains=["booking","payment"])
    with TestClient(create_app(cfg,transport=httpx.ASGITransport(app=upstream))) as client:
        assert client.post('/api/bookings',headers={"Idempotency-Key":"same-attempt"},json={}).status_code==200
        assert client.get('/api/payment/vnpay-ipn').status_code==200
    assert received==[("booking","/bookings","same-attempt"),("booking","/payment/vnpay-ipn",None)]


def test_payment_cutover_routes_callbacks_and_reconciliation_to_independent_store():
    upstream=FastAPI()
    @upstream.api_route('/{path:path}',methods=['GET','POST'])
    async def echo(request:Request):
        return {'owner':request.url.hostname,'path':request.url.path}
    cfg=GatewaySettings(_env_file=None,monolith_url='http://legacy',upstreams={'booking':'http://booking:8087','payment':'http://payment:8088'},enabled_domains=['booking','payment'])
    with TestClient(create_app(cfg,transport=httpx.ASGITransport(app=upstream))) as client:
        for path in ['/payment/vnpay-ipn','/admin/payment-reconciliation']:
            assert client.get('/api'+path).json()=={'owner':'payment','path':path}
        assert client.get('/api/bookings').json()['owner']=='booking'
