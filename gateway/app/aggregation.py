"""Preserve the admin reference contract while each owner authorizes its part."""
import asyncio
import httpx
from starlette.responses import JSONResponse
from .proxy import filtered_headers


async def admin_catalog(request, settings):
    request.state.upstream_domain = "aggregation"
    headers = filtered_headers(request.headers.raw, incoming=True)
    origins = (settings.origin_for("cinema") if "cinema" in settings.enabled_domains else settings.monolith_url, settings.origin_for("catalog"))
    replies = await asyncio.gather(*(
        request.app.state.upstream.get(origin+"/admin/catalog", headers=headers)
        for origin in origins), return_exceptions=True)
    result = {}
    for reply, keys in zip(replies, (("theaters", "rooms"), ("genres", "formats", "films"))):
        if isinstance(reply, Exception):
            return JSONResponse({"detail": "Admin references unavailable"}, status_code=503)
        if reply.status_code in {401, 403}:
            return JSONResponse({"detail": "Admin access denied"}, status_code=reply.status_code)
        if reply.status_code != 200:
            return JSONResponse({"detail": "Admin references unavailable"}, status_code=503)
        try:
            data = reply.json()
            if not isinstance(data, dict) or any(not isinstance(data.get(key), list) for key in keys):
                raise ValueError("Incomplete owner references")
            result.update({key: data[key] for key in keys})
        except (ValueError, TypeError):
            return JSONResponse({"detail": "Invalid admin reference response"}, status_code=503)
    return JSONResponse(result, headers={"X-Service-Name": "gateway"})
