"""Stream HTTP without decoding signed query strings or sharing user cookies."""

from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import Request
from starlette.background import BackgroundTask
from starlette.responses import JSONResponse, StreamingResponse

from .config import GatewaySettings
from .routing import owner

HOP_HEADERS = {
    b"connection", b"keep-alive", b"proxy-authenticate", b"proxy-authorization",
    b"te", b"trailer", b"transfer-encoding", b"upgrade", b"proxy-connection",
}
IDENTITY_HEADERS = {
    b"forwarded", b"x-request-id", b"x-real-ip", b"x-role", b"x-roles",
    b"x-permissions", b"x-service-key",
}


def filtered_headers(raw_headers, *, incoming: bool):
    connection_tokens = set()
    for key, value in raw_headers:
        if key.lower() == b"connection":
            connection_tokens.update(token.strip().lower() for token in value.split(b","))
    blocked = HOP_HEADERS | connection_tokens
    if incoming:
        blocked |= IDENTITY_HEADERS | {b"host"}
    result = []
    for key, value in raw_headers:
        name = key.lower()
        if name in blocked:
            continue
        if incoming and name.startswith((b"x-user", b"x-auth-", b"x-internal-", b"x-forwarded-")):
            continue
        result.append((name, value))
    return result


def public_location(value: bytes, upstream_origin: str) -> bytes:
    """Keep slash redirects inside /api; never rewrite external payment redirects."""
    location = value.decode("latin-1")
    parsed = urlsplit(location)
    upstream = urlsplit(upstream_origin)
    if parsed.netloc:
        if (parsed.scheme or upstream.scheme, parsed.netloc) != (upstream.scheme, upstream.netloc):
            return value
    elif parsed.scheme or not parsed.path.startswith("/"):
        return value
    path = "/api" + (parsed.path or "/")
    return urlunsplit(("", "", path, parsed.query, parsed.fragment)).encode("latin-1")


async def proxy_request(request: Request, settings: GatewaySettings):
    if request.url.path[len("/api"):].lstrip("/").split("/", 1)[0] == "internal":
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    domain = owner(request.url.path[len("/api"):])
    request.state.upstream_domain = domain if domain in settings.enabled_domains else "monolith"
    origin = settings.origin_for(domain)
    # raw_path retains escaped characters; query_string retains +, %xx, duplicates and order.
    raw_path = request.scope.get("raw_path", request.url.path.encode("utf-8"))
    path = raw_path[len(b"/api"):].split(b"?", 1)[0] or b"/"
    query = request.scope["query_string"]
    url = httpx.URL(origin).copy_with(
        raw_path=path + (b"?" + query if query else b"")
    )
    headers = filtered_headers(request.headers.raw, incoming=True)
    headers.append((b"x-request-id", request.state.request_id.encode("ascii")))
    # Do not build through AsyncClient: its cookie jar must never inject another user's cookies.
    outgoing = httpx.Request(
        request.method, url, headers=headers, content=request.stream(),
        extensions={"timeout": settings.timeout().as_dict()},
    )
    try:
        upstream = await request.app.state.upstream.send(outgoing, stream=True, follow_redirects=False)
    except httpx.TimeoutException:
        return JSONResponse({"detail": "Upstream request timed out"}, status_code=504)
    except httpx.RequestError:
        return JSONResponse({"detail": "Upstream service unavailable"}, status_code=502)

    async def stream_body():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()

    response = StreamingResponse(
        stream_body(), status_code=upstream.status_code,
        background=BackgroundTask(upstream.aclose),
    )
    # Preserve repeated Set-Cookie and the original encoding/content length of raw bytes.
    response.raw_headers = [
        (key, public_location(value, origin) if key == b"location" else value)
        for key, value in filtered_headers(upstream.headers.raw, incoming=False)
        if key != b"x-request-id"
    ]
    return response
