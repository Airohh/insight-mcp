"""BM25 search over corpus chunks.

The index lives in memory and is rebuilt from SQLite at startup — fine below
~10k chunks; a persistent index is a documented evolution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from insight_mcp.corpus import Corpus, IndexedChunk

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass(frozen=True)
class SearchResult:
    text: str
    score: float
    doc_id: int
    position: int
    title: str
    url: str
    date: str | None


class EmptyCorpusError(RuntimeError):
    """Raised when the corpus database has no indexed chunks."""


class SearchIndex:
    def __init__(self, corpus: Corpus):
        self._chunks: list[IndexedChunk] = corpus.indexed_chunks()
        if not self._chunks:
            raise EmptyCorpusError(
                "The corpus is empty. Run 'python scripts/ingest.py' to download"
                " and index the configured public URLs first."
            )
        self._bm25 = BM25Okapi([tokenize(c.text) for c in self._chunks])

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for i in ranked[:top_k]:
            c = self._chunks[i]
            results.append(
                SearchResult(
                    text=c.text,
                    score=round(float(scores[i]), 4),
                    doc_id=c.doc_id,
                    position=c.position,
                    title=c.title,
                    url=c.url,
                    date=c.date,
                )
            )
        return results
