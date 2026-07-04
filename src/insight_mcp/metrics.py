"""Prometheus metrics, one series per MCP tool.

Exposed at /metrics in HTTP mode (unauthenticated: it carries counts and
latencies, no corpus content — standard practice for scrape endpoints).
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram, make_asgi_app

TOOL_CALLS = Counter(
    "mcp_tool_calls_total",
    "Number of MCP tool calls",
    ["tool", "status"],
)

TOOL_DURATION = Histogram(
    "mcp_tool_duration_seconds",
    "MCP tool call duration in seconds",
    ["tool"],
)


def metrics_app():
    """ASGI app serving the Prometheus exposition format."""
    return make_asgi_app()
