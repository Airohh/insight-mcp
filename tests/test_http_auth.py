"""Auth middleware tested as plain ASGI, driven through httpx — no server."""

import asyncio

import httpx
import pytest

from insight_mcp.http_auth import BearerAuthMiddleware


async def ok_app(scope, receive, send):
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": b"ok"})


def request(app, path, headers=None) -> httpx.Response:
    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.get(path, headers=headers or {})

    return asyncio.run(go())


def test_rejects_missing_token():
    app = BearerAuthMiddleware(ok_app, "s3cret")
    resp = request(app, "/mcp")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


def test_rejects_wrong_token():
    app = BearerAuthMiddleware(ok_app, "s3cret")
    resp = request(app, "/mcp", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


def test_accepts_valid_token():
    app = BearerAuthMiddleware(ok_app, "s3cret")
    resp = request(app, "/mcp", headers={"Authorization": "Bearer s3cret"})
    assert resp.status_code == 200


def test_paths_outside_prefix_are_open():
    # /metrics (phase 4) and health probes must not require the MCP token
    app = BearerAuthMiddleware(ok_app, "s3cret")
    assert request(app, "/metrics").status_code == 200


def test_empty_token_refused_at_construction():
    with pytest.raises(ValueError, match="non-empty"):
        BearerAuthMiddleware(ok_app, "")
