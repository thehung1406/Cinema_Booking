"""Real owner APIs behind the gateway; no monolith or shared business database."""

from pathlib import Path
from types import SimpleNamespace
import json
import sys
from urllib.parse import urlsplit, parse_qsl

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
for owner in ["booking", "payment", "identity", "notification"]:
    sys.path.insert(0, str(ROOT / f"services/{owner}-service/tests"))

from payment_support import booking_store, ready, payment_store
from test_saga import pair, signed, deliver, event_from
from test_booking import request as booking_request
from identity_support import identity_store, identity_settings, identity_client
from notification_test_support import store
from cinema_platform.auth import AuthClient
from notification_service.delivery import receive
from notification_service.models import DeliveryJob
from gateway.app.config import GatewaySettings
from gateway.app.main import create_app


def test_real_identity_booking_payment_notification_through_gateway(
    pair, identity_client, identity_settings, store, monkeypatch
):
    class Owners(httpx.AsyncBaseTransport):
        async def handle_async_request(self, req):
            client = {
                "identity.test": identity_client,
                "booking.test": pair.bc,
                "payment.test": pair.pc,
            }[req.url.host]
            response = client.request(
                req.method,
                req.url.raw_path.decode(),
                headers=dict(req.headers),
                content=await req.aread(),
            )
            return httpx.Response(
                response.status_code,
                headers=response.headers,
                stream=httpx.ByteStream(response.content),
                request=req,
            )

    def introspect(req):
        response = identity_client.post(
            "/internal/v1/auth/introspect",
            headers={"X-Service-Key": identity_settings.service_key},
            json=json.loads(req.content),
        )
        return httpx.Response(response.status_code, json=response.json(), request=req)

    auth_http = httpx.AsyncClient(transport=httpx.MockTransport(introspect))
    auth = AuthClient(auth_http, "http://identity.test", identity_settings.service_key)
    pair.bc.app.state.auth = pair.pc.app.state.auth = auth

    def contact(user_id):
        result = identity_client.post(
            "/internal/v1/users/profiles",
            headers={"X-Service-Key": identity_settings.service_key},
            json={"user_ids": [user_id]},
        )
        assert result.status_code == 200
        return SimpleNamespace(**result.json()[0])

    monkeypatch.setattr("booking_service.bookings.contact", contact)
    cfg = GatewaySettings(
        legacy_enabled=False,
        upstreams={
            name: f"http://{name}.test" for name in ["identity", "booking", "payment"]
        },
        enabled_domains=["identity", "booking", "payment"],
        required_domains=["identity", "booking", "payment"],
        _env_file=None,
    )
    with TestClient(create_app(cfg, transport=Owners())) as http:
        body = dict(
            username="independent-customer",
            email="customer@example.com",
            password="Strong-owner-test-password",
            full_name="Customer",
        )
        customer = http.post("/api/auth/register", json=body)
        assert customer.status_code == 200
        uid = customer.json()["id"]
        token = http.post(
            "/api/auth/login", data={k: body[k] for k in ["username", "password"]}
        ).json()["access_token"]
        headers = {"Authorization": "Bearer " + token}
        assert http.get("/health/ready").status_code == 200
        assert (
            http.post(
                "/api/seats/hold", json=dict(showtime_id=1, seat_ids=[1, 2])
            ).status_code
            == 401
        )
        hold = http.post(
            "/api/seats/hold",
            headers=headers,
            json=dict(showtime_id=1, seat_ids=[1, 2]),
        )
        assert hold.status_code == 200, hold.text
        rid = hold.json()[0]["reservation_id"]
        checkout = http.post(
            "/api/bookings",
            headers={**headers, "Idempotency-Key": "gateway-owner-checkout"},
            json=booking_request(user=uid, reservation=rid).model_dump(mode="json"),
        )
        assert checkout.status_code == 201, checkout.text
        bid = checkout.json()["bookingId"]
        pay = http.post(
            "/api/payment/vnpay-url",
            headers=headers,
            json=dict(bookingId=bid, totalAmount=1),
        )
        assert pay.status_code == 200, pay.text
        params = dict(parse_qsl(urlsplit(pay.json()["paymentUrl"]).query))
        assert params["vnp_Amount"] == "15000000"
        receipt = signed(pair, params)
        assert (
            http.get("/api/payment/vnpay-ipn", params=receipt).json()["RspCode"] == "00"
        )
        assert (
            http.get("/api/payment/vnpay-ipn", params=receipt).json()["RspCode"] == "02"
        )
        assert http.get(f"/api/tickets/booking/{bid}", headers=headers).json() == []
        deliver(pair)
        tickets = http.get(f"/api/tickets/booking/{bid}", headers=headers).json()
        assert len(tickets) == 2 and len({t["ticket_code"] for t in tickets}) == 2
        event = event_from(pair.book, "BookingConfirmationEmailRequested.v1")
        with Session(store) as db, db.begin():
            receive(db, event)
        with Session(store) as db, db.begin():
            receive(db, event)
        with Session(store) as db:
            assert db.scalar(select(func.count()).select_from(DeliveryJob)) == 1
        # Current Identity session revocation reaches both independently owned APIs.
        assert http.post("/api/auth/logout", headers=headers).status_code == 200
        assert (
            http.get(f"/api/tickets/booking/{bid}", headers=headers).status_code == 401
        )
        assert (
            http.get(f"/api/payment/status/{bid}", headers=headers).status_code == 401
        )
        assert http.get("/api/seats/showtime/1").status_code == 200
