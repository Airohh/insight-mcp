# insight-mcp

[![CI](https://github.com/Airohh/insight-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Airohh/insight-mcp/actions/workflows/ci.yml)

Self-contained MCP (Model Context Protocol) server exposing hybrid document search
as tools for AI agents (Claude Code, Claude Desktop, Anthropic API).

The server does **retrieval only** (BM25, then hybrid): it returns passages, scores
and sources — the MCP client (the LLM) writes the cited answer. No inference cost,
no API key on the server side.

**Works out of the box**: on first start, if no corpus exists, the server seeds a
small bundled demo corpus (original texts, committed with the repo) so the tools
answer immediately — no network, no ingestion step. Index a real corpus whenever
you want with `scripts/ingest.py` (URL list or sitemap, fully configurable).

## Features

- **3 tools** (`search_publications`, `get_publication`, `list_topics`), 2 MCP
  resources, 1 grounded-answer prompt
- **Two search modes**: BM25 (default, zero deps) or hybrid BM25 + dense
  embeddings fused with Reciprocal Rank Fusion (`pip install .[hybrid]`)
- **Two transports**: stdio (local clients) and Streamable HTTP (remote, :8020)
- **MCPOps built in**: structured JSON logs, Prometheus metrics per tool
  (`/metrics`), bearer auth, per-token rate limiting, Docker, CI/CD

## Architecture

```
MCP client (Claude Code / Desktop / API)      ← the client GENERATES (cited answers)
        │ stdio / Streamable HTTP (:8020, phase 3)
        ▼
    insight-mcp (FastMCP)
        │ local index: BM25 (+ dense, phase 2), SQLite
        ▼
    data/ (gitignored) ← scripts/ingest.py ← public URLs (configurable corpus)
```

The corpus is configurable (URL list / sitemap). Indexed content is **never
committed** — the repo ships code and seed URLs only. Ingestion is polite:
robots.txt honored, identifiable User-Agent, ~1 req/s, disk cache.

## Tools

| Tool | Arguments | Returns |
|------|-----------|---------|
| `search_publications` | `query`, `top_k=5` | most relevant passages + relevance scores + source (title, url, date) |
| `get_publication` | `doc_id` | full text + metadata of one publication |
| `list_topics` | — | corpus overview: counts + every publication's id/title/date/url |

Also exposed over MCP: resources `corpus://stats` and `corpus://health`, and the
`grounded_answer` prompt (answer only from retrieved passages, cite title + url).

## Search modes

| Mode | How | When |
|------|-----|------|
| `bm25` (default) | lexical, pure Python, zero extra deps | exact terms, acronyms, product names |
| `hybrid` | BM25 + dense embeddings (fastembed, ONNX — no torch), fused with Reciprocal Rank Fusion | paraphrased questions that share few words with the text |

```powershell
pip install -e ".[hybrid]"
# .env: SEARCH_MODE=hybrid  (first run downloads the ONNX model, ~30 MB)
```

Example on the demo corpus: for *"zero trust identity strategy"* both modes rank
the Continuous Identity publication first, but hybrid also surfaces the digital
wallets & IAM publication — no shared keywords, pure semantic match. Trade-off:
hybrid adds model load at startup and an embedding pass per query; BM25 stays
dependency-free and instant.

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
python -m insight_mcp.server   # works immediately (bundled demo corpus)
```

### Index a real corpus (optional)

```powershell
# From the seed URL list (scripts/seed_urls_wavestone.txt by default):
python scripts/ingest.py

# Or any corpus from a sitemap:
python scripts/ingest.py --sitemap https://example.com/sitemap.xml --filter=/blog/ --max-docs 50
```

Ingestion is polite (robots.txt, identifiable User-Agent, ~1 req/s, disk cache)
and the downloaded content stays in `data/` — never committed.

### Plug into Claude Code

```powershell
claude mcp add insight -- <absolute-path-to>\.venv\Scripts\python.exe -m insight_mcp.server
```

Then ask e.g. *"What does this corpus say about AI agents in the enterprise?"* —
Claude calls `search_publications` and answers with cited sources.

### Plug into Claude Desktop

`claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "insight": {
      "command": "C:\\path\\to\\insight-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "insight_mcp.server"]
    }
  }
}
```

Use the venv's absolute python path — Claude Desktop spawns the server itself
and does not activate virtualenvs.

### Demo scenario

1. Ingest the demo corpus (`python scripts/ingest.py`), plug into Claude Code or Desktop.
2. Ask: *"According to the indexed publications, how should companies govern
   autonomous AI agents? Cite your sources."*
3. Claude calls `search_publications`, then answers with passages cited as
   *title (url)* — every claim traceable to a public publication.

### Inspect without a client

```powershell
npx @modelcontextprotocol/inspector python -m insight_mcp.server
```

Every tool call is logged as structured JSON on stderr (tool, duration ms,
status, response size) — stdout stays clean for the stdio transport.

## Remote (Streamable HTTP)

```powershell
# .env: MCP_AUTH_TOKEN=<strong-secret>   ('changeme' is refused)
python -m insight_mcp.server --http      # serves http://0.0.0.0:8020/mcp
```

Requests to `/mcp` without `Authorization: Bearer <token>` get 401. The token
is compared constant-time and never logged. A static bearer token fits a demo
deployment; OAuth 2.1 via the MCP SDK's auth hooks is the documented next step.

### Docker

```powershell
docker compose up --build
# or bare:
docker run -p 8020:8020 -e MCP_AUTH_TOKEN=<secret> -v ${PWD}/data:/app/data insight-mcp
```

The image contains **code only — never the corpus** (indexed third-party
content is not redistributed). Provide data at runtime: mount `data/` as a
volume, or set `INGEST_ON_BOOT=1` to build the index from the seed URLs when
the container starts.

### Consume from the Anthropic API (MCP connector)

Once deployed behind HTTPS, any Claude API call can use the server directly —
no MCP client needed:

```powershell
python scripts/demo_mcp_connector.py --url https://<host>/mcp --token <secret>
```

Uses the `mcp-client-2025-11-20` beta: the request declares the server under
`mcp_servers` and enables its tools with an `mcp_toolset` entry.

## MCPOps

Operating the server is part of the design, not an afterthought:

| Concern | Implementation |
|---------|----------------|
| Logging | one JSON line per tool call on stderr: tool, duration ms, status, response size (Authorization never logged) |
| Metrics | Prometheus at `/metrics`: `mcp_tool_calls_total{tool,status}`, `mcp_tool_duration_seconds{tool}` histogram |
| Auth | constant-time bearer token on `/mcp`; weak defaults refused at startup |
| Rate limiting | sliding window per token (`RATE_LIMIT_PER_MINUTE`, default 60; in-memory — Redis is the multi-replica evolution) |
| Health | `corpus://health` MCP resource + open `/metrics` for probes |
| CI/CD | ruff + pytest on 3.11/3.12 + Docker build on every push; GHCR publish on version tags |

## Corpus & content rights

Indexed third-party content is **never committed and never baked into a Docker
image** — the repo ships code, seed URLs, and a small bundled demo corpus of
original texts. See `docs/architecture.md` for the full decision log.
