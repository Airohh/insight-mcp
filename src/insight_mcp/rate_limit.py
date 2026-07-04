"""In-memory sliding-window rate limiting for the HTTP transport.

Keyed by a hash of the Authorization header (per-token limit; the raw token is
never stored). In-memory state means the limit is per-process — a multi-replica
deployment needs a shared store (Redis) instead; documented evolution.
"""

from __future__ import annotations

import hashlib
import time
from collections import deque
from typing import Any

from insight_mcp.http_auth import Receive, Scope, Send


class RateLimitMiddleware:
    def __init__(
        self,
        app: Any,
        limit: int,
        window_seconds: float = 60.0,
        protect_prefix: str = "/mcp",
    ):
        if limit <= 0:
            raise ValueError("limit must be positive; omit the middleware to disable")
        self._app = app
        self._limit = limit
        self._window = window_seconds
        self._prefix = protect_prefix
        self._hits: dict[str, deque[float]] = {}

    def _key(self, scope: Scope) -> str:
        auth = next(
            (v for k, v in scope.get("headers", []) if k == b"authorization"), b""
        )
        return hashlib.sha256(auth).hexdigest()

    def _allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] > self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith(self._prefix):
            if not self._allow(self._key(scope)):
                await send(
                    {
                        "type": "http.response.start",
                        "status": 429,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"retry-after", str(int(self._window)).encode()),
                        ],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b'{"error": "rate limit exceeded"}',
                    }
                )
                return
        await self._app(scope, receive, send)
