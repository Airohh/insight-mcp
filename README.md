# insight-mcp

Self-contained MCP (Model Context Protocol) server exposing hybrid document search
as tools for AI agents (Claude Code, Claude Desktop, Anthropic API).

The server does **retrieval only** (BM25, then hybrid): it returns passages, scores
and sources — the MCP client (the LLM) writes the cited answer. No inference cost,
no API key on the server side.

> Work in progress.

## Roadmap

- **Phase 1** — ingestion (public URLs → SQLite), BM25 index, 3 MCP tools over stdio *(in progress)*
- **Phase 2** — hybrid search (fastembed + RRF fusion), MCP resources & prompt
- **Phase 3** — remote: Streamable HTTP (:8020), Docker, cloud deployment
- **Phase 4** — MCPOps: Prometheus metrics per tool, rate limiting

## Architecture

```
MCP client (Claude Code / Desktop / API)      ← the client GENERATES (cited answers)
        │ stdio / Streamable HTTP (:8020)
        ▼
    insight-mcp (FastMCP)
        │ local index: BM25 (+ dense, phase 2), SQLite
        ▼
    data/ (gitignored) ← scripts/ingest.py ← public URLs (configurable corpus)
```

The corpus is configurable (URL list / sitemap). Indexed content is **never
committed** — the repo ships code and seed URLs only.

## Quick start (dev)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```
