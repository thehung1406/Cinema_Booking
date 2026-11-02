import asyncio

import httpx
import pytest
from cinema_platform.auth import AuthClient, AuthError

KEY = "isolated-internal-service-key-for-tests-only"


def test_identity_timeout_and_malformed_response_fail_closed():
    async def run(handler):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(AuthError) as failure:
                await AuthClient(client, "http://identity", KEY).introspect("token", "notifications.manage")
            assert failure.value.status_code == 503
    asyncio.run(run(lambda request: httpx.Response(200, json={"role": "ADMIN"})))
    def timeout(request):
        raise httpx.ReadTimeout("private connection", request=request)
    asyncio.run(run(timeout))


def test_permissions_and_active_account_are_checked_on_every_call():
    state = {"user_id": 1, "role": "ADMIN", "permissions": ["notifications.manage"], "is_active": True}
    calls = []
    def handler(request):
        calls.append(request)
        assert request.headers["x-service-key"] == KEY
        return httpx.Response(200, json=state)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = AuthClient(client, "http://identity", KEY)
            assert (await adapter.introspect("token", "notifications.manage")).user_id == 1
            state["permissions"] = []
            with pytest.raises(AuthError) as failure:
                await adapter.introspect("token", "notifications.manage")
            assert failure.value.status_code == 403
            state["is_active"] = False
            with pytest.raises(AuthError) as failure:
                await adapter.introspect("token")
            assert failure.value.status_code == 403
    asyncio.run(run())
    assert len(calls) == 3


@pytest.mark.parametrize("status,expected", [(401,401),(403,403),(404,503),(500,503),(307,503)])
def test_identity_http_errors_are_not_treated_as_authenticated(status, expected):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(status))) as client:
            with pytest.raises(AuthError) as failure:
                await AuthClient(client, "http://identity", KEY).introspect("token")
            assert failure.value.status_code == expected
    asyncio.run(run())
