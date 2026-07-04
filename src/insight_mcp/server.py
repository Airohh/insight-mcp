"""FastMCP server exposing the indexed corpus as tools.

The server does retrieval only: it returns passages, scores and sources, and
the MCP client (the LLM) writes the cited answer. Run with:

    python -m insight_mcp.server          # stdio (Claude Code / Desktop)
    python -m insight_mcp.server --http   # Streamable HTTP on MCP_PORT (remote)
"""

from __future__ import annotations

import argparse
import functools
import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from mcp.server.fastmcp import FastMCP

from insight_mcp.corpus import Corpus
from insight_mcp.logging_conf import setup_logging
from insight_mcp.metrics import TOOL_CALLS, TOOL_DURATION
from insight_mcp.search import SearchIndex
from insight_mcp.settings import get_settings

log = logging.getLogger(__name__)

mcp = FastMCP("insight-mcp")

MAX_TOP_K = 20
MAX_DOC_CHARS = 20_000

_corpus: Corpus | None = None
_index: SearchIndex | None = None
# Tools run in a worker thread pool: guard lazy init (and serialize the
# shared SQLite connection, opened with check_same_thread=False).
_init_lock = threading.Lock()


def _get_corpus() -> Corpus:
    global _corpus
    with _init_lock:
        if _corpus is None:
            settings = get_settings()
            if not settings.db_path.exists():
                # Zero-setup path: a fresh clone gets the bundled sample corpus
                # so the tools work immediately; scripts/ingest.py replaces it.
                from insight_mcp.bootstrap import seed_sample_corpus

                _corpus = seed_sample_corpus(settings.db_path)
            else:
                _corpus = Corpus(settings.db_path)
        return _corpus


def _get_index() -> SearchIndex:
    global _index
    corpus = _get_corpus()
    with _init_lock:
        if _index is None:
            settings = get_settings()
            embedder = None
            if settings.search_mode == "hybrid":
                from insight_mcp.search import fastembed_embedder

                embedder = fastembed_embedder(settings.embed_model)
            _index = SearchIndex(corpus, mode=settings.search_mode, embedder=embedder)
            log.info("index_ready", extra={"mode": _index.mode})
        return _index


def _logged(func: Callable[..., Any]) -> Callable[..., Any]:
    """Log and measure every tool call: JSON log line + Prometheus series."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            duration = time.perf_counter() - start
            TOOL_CALLS.labels(tool=func.__name__, status="error").inc()
            TOOL_DURATION.labels(tool=func.__name__).observe(duration)
            log.info(
                "tool_call",
                extra={
                    "tool": func.__name__,
                    "duration_ms": round(duration * 1000, 1),
                    "status": "error",
                    "error": str(exc),
                },
            )
            raise
        duration = time.perf_counter() - start
        TOOL_CALLS.labels(tool=func.__name__, status="ok").inc()
        TOOL_DURATION.labels(tool=func.__name__).observe(duration)
        log.info(
            "tool_call",
            extra={
                "tool": func.__name__,
                "duration_ms": round(duration * 1000, 1),
                "status": "ok",
                "response_chars": len(json.dumps(result, default=str)),
            },
        )
        return result

    return wrapper


@mcp.tool()
@_logged
def search_publications(query: str, top_k: int = 5) -> list[dict]:
    """Search the indexed publication corpus and return the most relevant passages.

    Use this tool whenever the question is about topics, positions, facts or
    trends covered by the indexed publications (e.g. "what does this corpus say
    about AI agents in the enterprise?"). Prefer it over get_publication for any
    topical question; only fall back to get_publication when a returned passage
    needs its full surrounding document.

    Each result contains the passage text, its BM25 relevance score, and the
    source publication (doc_id, title, url, date). Cite title + url when using
    a passage in an answer.
    """
    top_k = max(1, min(int(top_k), MAX_TOP_K))
    return [asdict(r) for r in _get_index().search(query, top_k=top_k)]


@mcp.tool()
@_logged
def get_publication(doc_id: int) -> dict:
    """Return the full text and metadata of one publication by its doc_id.

    Use this after search_publications when a passage is promising but truncated,
    or when the user asks to summarize a specific publication in full. The
    doc_id comes from search_publications or list_topics results.
    """
    doc = _get_corpus().get_document(int(doc_id))
    if doc is None:
        raise ValueError(
            f"No publication with doc_id={doc_id}. Use list_topics or"
            " search_publications to find valid ids."
        )
    # Cap the payload so one long document cannot flood the client's context
    if len(doc["text"]) > MAX_DOC_CHARS:
        doc["text"] = doc["text"][:MAX_DOC_CHARS]
        doc["text_truncated"] = True
    return doc


@mcp.tool()
@_logged
def list_topics() -> dict:
    """List what the corpus contains: document count and every publication's
    id, title, date and url.

    Use this when the user asks what the corpus covers, which publications are
    available, or when you need a valid doc_id and search_publications has not
    returned one.
    """
    corpus = _get_corpus()
    return {
        **corpus.stats(),
        "publications": [
            {"doc_id": d.id, "title": d.title, "date": d.date, "url": d.url}
            for d in corpus.documents()
        ],
    }


@mcp.resource("corpus://stats")
def corpus_stats() -> str:
    """Corpus statistics: document/chunk counts, date range, active search mode."""
    corpus = _get_corpus()
    dates = [d.date for d in corpus.documents() if d.date]
    return json.dumps(
        {
            **corpus.stats(),
            "oldest_date": min(dates, default=None),
            "latest_date": max(dates, default=None),
            "search_mode": get_settings().search_mode,
        }
    )


@mcp.resource("corpus://health")
def corpus_health() -> str:
    """Liveness of the corpus database and the in-memory search index."""
    try:
        stats = _get_corpus().stats()
        _get_index()
    except Exception as exc:  # surface the failure instead of crashing the read
        return json.dumps({"status": "error", "detail": str(exc)})
    status = "ok" if stats["chunks"] > 0 else "empty"
    return json.dumps({"status": status, **stats})


@mcp.prompt()
def grounded_answer(question: str) -> str:
    """Answer a question strictly from the indexed publications, with citations."""
    return (
        "Answer the question below using ONLY passages returned by the"
        " search_publications tool (call it first; refine the query and call it"
        " again if the first results are weak). Every claim in your answer must"
        " cite its source publication as: title (url). If the returned passages"
        " do not cover the question, say so explicitly instead of guessing."
        f"\n\nQuestion: {question}"
    )


def run_http() -> None:
    """Serve Streamable HTTP on 0.0.0.0:MCP_PORT, path /mcp, bearer auth."""
    import uvicorn
    from starlette.routing import Mount

    from insight_mcp.http_auth import BearerAuthMiddleware
    from insight_mcp.metrics import metrics_app
    from insight_mcp.rate_limit import RateLimitMiddleware

    settings = get_settings()
    if not settings.mcp_auth_token or settings.mcp_auth_token == "changeme":
        raise SystemExit(
            "HTTP mode requires a real MCP_AUTH_TOKEN (set it in .env;"
            " 'changeme' is refused on purpose)."
        )
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = settings.mcp_port
    mcp.settings.streamable_http_path = "/mcp"
    # Stateless: no per-session state on the server, so it survives restarts
    # and scales horizontally (each request is self-contained).
    mcp.settings.stateless_http = True
    inner = mcp.streamable_http_app()
    # /metrics stays outside auth and rate limiting: counts and latencies only
    inner.routes.append(Mount("/metrics", app=metrics_app()))
    app: Any = BearerAuthMiddleware(inner, settings.mcp_auth_token)
    if settings.rate_limit_per_minute > 0:
        app = RateLimitMiddleware(app, limit=settings.rate_limit_per_minute)
    log.info(
        "server_start",
        extra={"transport": "streamable-http", "port": settings.mcp_port},
    )
    uvicorn.run(app, host="0.0.0.0", port=settings.mcp_port, log_config=None)


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="insight-mcp server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="serve Streamable HTTP on MCP_PORT instead of stdio",
    )
    args = parser.parse_args()
    if args.http:
        run_http()
        return
    log.info("server_start", extra={"transport": "stdio"})
    mcp.run()


if __name__ == "__main__":
    main()
