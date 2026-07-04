"""FastMCP server exposing the indexed corpus as tools.

The server does retrieval only: it returns passages, scores and sources, and
the MCP client (the LLM) writes the cited answer. Run with:

    python -m insight_mcp.server
"""

from __future__ import annotations

import functools
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from insight_mcp.corpus import Corpus
from insight_mcp.logging_conf import setup_logging
from insight_mcp.search import SearchIndex
from insight_mcp.settings import get_settings

log = logging.getLogger(__name__)

mcp = FastMCP("insight-mcp")

MAX_TOP_K = 20

_corpus: Corpus | None = None
_index: SearchIndex | None = None


def _get_corpus() -> Corpus:
    global _corpus
    if _corpus is None:
        settings = get_settings()
        if not settings.db_path.exists():
            raise RuntimeError(
                f"Corpus database not found at {settings.db_path}."
                " Run 'python scripts/ingest.py' to build it first."
            )
        _corpus = Corpus(settings.db_path)
    return _corpus


def _get_index() -> SearchIndex:
    global _index
    if _index is None:
        _index = SearchIndex(_get_corpus())
    return _index


def _logged(func: Callable[..., Any]) -> Callable[..., Any]:
    """Log every tool call: name, duration ms, status, response size."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            log.info(
                "tool_call",
                extra={
                    "tool": func.__name__,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                    "status": "error",
                    "error": str(exc),
                },
            )
            raise
        log.info(
            "tool_call",
            extra={
                "tool": func.__name__,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
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
    results = _get_index().search(query, top_k=top_k)
    return [
        {
            "text": r.text,
            "score": r.score,
            "doc_id": r.doc_id,
            "title": r.title,
            "url": r.url,
            "date": r.date,
        }
        for r in results
    ]


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


def main() -> None:
    setup_logging()
    log.info("server_start", extra={"transport": "stdio"})
    mcp.run()


if __name__ == "__main__":
    main()
