"""Phase 4 ops: Prometheus metrics wiring and rate limiting."""

import asyncio

import httpx
import pytest
from prometheus_client import REGISTRY

import insight_mcp.server as server
from insight_mcp.rate_limit import RateLimitMiddleware
from insight_mcp.search import SearchIndex


@pytest.fixture()
def wired_server(corpus, monkeypatch):
    monkeypatch.setattr(server, "_corpus", corpus)
    monkeypatch.setattr(server, "_index", SearchIndex(corpus))
    return server


def _counter(tool: str, status: str) -> float:
    return (
        REGISTRY.get_sample_value(
            "mcp_tool_calls_total", {"tool": tool, "status": status}
        )
        or 0.0
    )


def test_tool_call_increments_metrics(wired_server):
    before = _counter("search_publications", "ok")
    wired_server.search_publications("cloud")
    assert _counter("search_publications", "ok") == before + 1


def test_tool_error_increments_error_metric(wired_server):
    before = _counter("get_publication", "error")
    with pytest.raises(ValueError):
        wired_server.get_publication(999)
    assert _counter("get_publication", "error") == before + 1


# --- rate limiting ---


async def ok_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def get(app, path, headers=None) -> httpx.Response:
    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.get(path, headers=headers or {})

    return asyncio.run(go())


def test_rate_limit_returns_429_after_limit():
    app = RateLimitMiddleware(ok_app, limit=3)
    headers = {"Authorization": "Bearer x"}
    for _ in range(3):
        assert get(app, "/mcp", headers).status_code == 200
    resp = get(app, "/mcp", headers)
    assert resp.status_code == 429
    assert "retry-after" in resp.headers


def test_rate_limit_is_per_token():
    app = RateLimitMiddleware(ok_app, limit=1)
    assert get(app, "/mcp", {"Authorization": "Bearer a"}).status_code == 200
    assert get(app, "/mcp", {"Authorization": "Bearer b"}).status_code == 200
    assert get(app, "/mcp", {"Authorization": "Bearer a"}).status_code == 429


def test_rate_limit_ignores_other_paths():
    app = RateLimitMiddleware(ok_app, limit=1)
    for _ in range(5):
        assert get(app, "/metrics").status_code == 200


def test_rate_limit_rejects_nonpositive_limit():
    with pytest.raises(ValueError, match="positive"):
        RateLimitMiddleware(ok_app, limit=0)
