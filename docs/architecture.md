# Architecture & decisions

```
┌──────────────┐  stdio / Streamable HTTP    ┌──────────────────────────────┐
│ MCP client   │ ──────────────────────────► │  insight-mcp (FastMCP :8020) │
│ (Claude Code,│                             │  ┌────────────────────────┐  │
│  Desktop,    │ ◄────────────────────────── │  │ in-memory index        │  │
│  API)        │  passages + scores + sources│  │ BM25 (+ dense hybrid)  │  │
└──────────────┘                             │  │ SQLite: data/corpus.db │  │
   ▲ the client GENERATES                    │  └────────────────────────┘  │
   │ (answer + citations)                    │  /metrics → Prometheus       │
                                             └──────────────▲───────────────┘
                                                            │ offline ingestion
                                                 scripts/ingest.py ─► public URLs
                                                 (httpx + trafilatura, polite, cached)
```

## Tool contract

| Tool | Input | Output |
|------|-------|--------|
| `search_publications` | `query, top_k=5` | passages + scores + {title, url, date} |
| `get_publication` | `doc_id` | full text (capped at 20k chars) + metadata |
| `list_topics` | — | corpus overview (counts, titles, dates, urls) |

Plus MCP resources `corpus://stats` and `corpus://health`, and the
`grounded_answer` prompt (answer only from retrieved passages, cite title + url).

## Decisions

### Retrieval-only, not a full RAG service

In an MCP architecture the LLM already lives on the client. The server exposes
knowledge only — passages, relevance scores, sources — and the client writes the
cited answer. Consequences: no model API key on the server, zero inference
cost, and the whole system is reproducible by anyone who clones the repo.
A full RAG service (server-side generation) would duplicate the client's model
and force key management onto the server for no retrieval-quality gain.

### BM25 first, hybrid as an opt-in

BM25 (rank-bm25, pure Python) covers exact-term queries with zero heavy
dependencies and instant startup. Hybrid mode adds fastembed (ONNX runtime, no
torch) and fuses both rankings with Reciprocal Rank Fusion (`1/(k+rank)`,
k=60). The embedder is injected as a plain callable, so tests exercise the
dense path with a deterministic fake and CI never downloads a model.
Trade-off: hybrid pays model load at startup and one embedding pass per query;
it wins on paraphrased questions that share no vocabulary with the text.

### In-memory index, rebuilt at startup

The BM25 index (and dense vectors in hybrid mode) are rebuilt from SQLite when
the first tool runs. Fine below ~10k chunks; a persistent vector index
(e.g. sqlite-vec, Qdrant) is the documented evolution once corpora grow.

### Bundled sample corpus for zero-setup startup

If `data/corpus.db` does not exist, the server seeds five short original texts
(committed in `sample_corpus.py`) so a fresh clone answers immediately with no
network and no ingestion step. Running `scripts/ingest.py` replaces the sample
with a real corpus. This keeps the demo instant while keeping real content
acquisition explicit and configurable.

### Streamable HTTP over SSE, stateless

The MCP spec's current remote transport is Streamable HTTP; SSE is the legacy
option. The server runs `stateless_http=True`: every request is self-contained,
so the process survives restarts and scales horizontally without session
affinity. Cost: no server-initiated notifications, which retrieval tools don't
need.

### Auth: static bearer token

A single `MCP_AUTH_TOKEN` compared in constant time (`hmac.compare_digest`)
protects `/mcp`; the value is never logged and `changeme`/empty are refused at
startup. Right-sized for a demo deployment with one consumer. The evolution is
OAuth 2.1 via the MCP SDK's `token_verifier` hooks — worth discussing, not
worth building before there are multiple clients.

### Rate limiting: in-memory sliding window

Per-token (hash of the Authorization header), 60 req/min by default
(`RATE_LIMIT_PER_MINUTE`, 0 disables). In-memory means per-process: a
multi-replica deployment needs a shared store (Redis). Kept deliberately
simple; the middleware boundary makes the swap local.

### Corpus & content rights

Indexed third-party content is never committed and never enters a published
Docker image (an image on a registry is redistribution). The repo ships code,
seed URLs and original sample texts only. At runtime the corpus arrives via a
mounted volume or `INGEST_ON_BOOT=1` (the container downloads from the
configured public URLs itself). Ingestion honors robots.txt, sends an
identifiable User-Agent, rate-limits to ~1 req/s and caches to disk.

## Known limits

- Index rebuild on every start — no incremental updates.
- Single SQLite connection shared across the tool thread pool (serialized by a
  lock); fine at demo scale, a connection pool is the evolution.
- Rate limiting and metrics are per-process (see above).
- `get_publication` truncates documents at 20k chars to protect client context.
