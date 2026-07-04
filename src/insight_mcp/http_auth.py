"""Bearer-token ASGI middleware for the Streamable HTTP transport.

A static token is deliberately simple: it protects a demo deployment without
an identity provider. The documented next step is OAuth 2.1 via the MCP SDK's
`auth_server_provider` / `token_verifier` hooks.
"""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable
from typing import Any

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


class BearerAuthMiddleware:
    """Reject requests under `protect_prefix` without the expected bearer token.

    Comparison is constant-time; the received header value is never logged.
    """

    def __init__(self, app: Any, token: str, protect_prefix: str = "/mcp"):
        if not token:
            raise ValueError("auth token must be non-empty")
        self._app = app
        self._expected = f"Bearer {token}".encode()
        self._prefix = protect_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith(self._prefix):
            auth = next(
                (v for k, v in scope.get("headers", []) if k == b"authorization"),
                b"",
            )
            if not hmac.compare_digest(auth, self._expected):
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"www-authenticate", b"Bearer"),
                        ],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b'{"error": "unauthorized"}',
                    }
                )
                return
        await self._app(scope, receive, send)
