"""End-to-end demo: Claude consumes the remote insight-mcp server via the
Anthropic API MCP connector (no local MCP client involved).

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python scripts/demo_mcp_connector.py --url https://<host>/mcp --token <MCP_AUTH_TOKEN>

Requires the server to run in HTTP mode (python -m insight_mcp.server --http)
behind HTTPS — the connector only accepts https:// URLs, so point it at the
deployed instance (or a TLS tunnel), not http://localhost.
"""

from __future__ import annotations

import argparse
import os
import sys

import anthropic

QUESTION = (
    "According to the indexed publications, how should companies govern"
    " autonomous AI agents? Cite each claim as: title (url)."
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="server URL, e.g. https://host/mcp")
    parser.add_argument(
        "--token",
        default=os.environ.get("MCP_AUTH_TOKEN", ""),
        help="bearer token (defaults to MCP_AUTH_TOKEN env var)",
    )
    parser.add_argument("--question", default=QUESTION)
    args = parser.parse_args()
    if not args.token:
        print("Missing token: pass --token or set MCP_AUTH_TOKEN.", file=sys.stderr)
        return 1

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": args.question}],
        mcp_servers=[
            {
                "type": "url",
                "url": args.url,
                "name": "insight",
                "authorization_token": args.token,
            }
        ],
        tools=[{"type": "mcp_toolset", "mcp_server_name": "insight"}],
        betas=["mcp-client-2025-11-20"],
    )

    for block in response.content:
        if block.type == "mcp_tool_use":
            print(f"[tool call] {block.name}({block.input})", file=sys.stderr)
        elif block.type == "text":
            print(block.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
