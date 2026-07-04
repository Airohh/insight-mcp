# insight-mcp

Self-contained MCP (Model Context Protocol) server exposing hybrid document search
as tools for AI agents (Claude Code, Claude Desktop, Anthropic API).

The server does **retrieval only** (BM25, then hybrid): it returns passages, scores
and sources — the MCP client (the LLM) writes the cited answer. No inference cost,
no API key on the server side.

## Roadmap

- **Phase 1** — ingestion (public URLs → SQLite), BM25 index, 3 MCP tools over stdio ✅
- **Phase 2** — hybrid search (fastembed + RRF fusion), MCP resources & prompt
- **Phase 3** — remote: Streamable HTTP (:8020), Docker, cloud deployment
- **Phase 4** — MCPOps: Prometheus metrics per tool, rate limiting

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
| `search_publications` | `query`, `top_k=5` | most relevant passages + BM25 scores + source (title, url, date) |
| `get_publication` | `doc_id` | full text + metadata of one publication |
| `list_topics` | — | corpus overview: counts + every publication's id/title/date/url |

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest

# Build the demo corpus (Wavestone public insights, ~30 pages, ~1 min)
python scripts/ingest.py

# Or any corpus from a sitemap:
python scripts/ingest.py --sitemap https://example.com/sitemap.xml --filter=/blog/ --max-docs 50
```

### Plug into Claude Code

```powershell
claude mcp add insight -- <absolute-path-to>\.venv\Scripts\python.exe -m insight_mcp.server
```

Then ask e.g. *"What does this corpus say about AI agents in the enterprise?"* —
Claude calls `search_publications` and answers with cited sources.

### Inspect without a client

```powershell
npx @modelcontextprotocol/inspector python -m insight_mcp.server
```

Every tool call is logged as structured JSON on stderr (tool, duration ms,
status, response size) — stdout stays clean for the stdio transport.
