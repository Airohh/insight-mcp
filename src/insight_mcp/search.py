"""Search over corpus chunks: BM25, or hybrid BM25 + dense embeddings.

The index lives in memory and is rebuilt from SQLite at startup — fine below
~10k chunks; a persistent index is a documented evolution.

Hybrid mode fuses the BM25 ranking with a dense (cosine) ranking using
Reciprocal Rank Fusion. Embeddings come from fastembed (ONNX runtime, no
torch); the embedder is injected as a plain callable so tests can substitute
a deterministic fake and CI never downloads a model.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi

from insight_mcp.corpus import Corpus

log = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

# Standard dampening constant from the RRF paper (Cormack et al., 2009):
# large enough that a document must rank well in a list to gain much score.
RRF_K = 60

# An embedder maps a batch of texts to a (n, dim) float array.
Embedder = Callable[[Sequence[str]], np.ndarray]


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


def fastembed_embedder(model_name: str) -> Embedder:
    """Build an embedder backed by fastembed.

    Imported lazily so bm25 mode works without the optional dependency
    (`pip install .[hybrid]`). The first call downloads the ONNX model to the
    local HuggingFace cache.
    """
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name)

    def embed(texts: Sequence[str]) -> np.ndarray:
        return np.array(list(model.embed(list(texts))), dtype=np.float32)

    return embed


def rrf_fuse(rankings: Sequence[Sequence[int]], k: int = RRF_K) -> dict[int, float]:
    """Reciprocal Rank Fusion: score(d) = sum over lists of 1 / (k + rank).

    Ranks are 1-based; documents absent from a list contribute nothing for it.
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
    return scores


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


class SearchIndex:
    def __init__(
        self,
        corpus: Corpus,
        mode: str = "bm25",
        embedder: Embedder | None = None,
    ):
        self._chunks = corpus.indexed_chunks()
        if not self._chunks:
            raise EmptyCorpusError(
                "The corpus is empty. Run 'python scripts/ingest.py' to download"
                " and index the configured public URLs first."
            )
        self._bm25 = BM25Okapi([tokenize(c.text) for c in self._chunks])
        self._mode = mode
        self._embedder = embedder
        self._vectors: np.ndarray | None = None
        if mode == "hybrid":
            if embedder is None:
                raise ValueError("hybrid mode requires an embedder")
            self._vectors = _normalize(embedder([c.text for c in self._chunks]))
            log.info(
                "dense_index_built",
                extra={"chunks": len(self._chunks), "dim": self._vectors.shape[1]},
            )

    @property
    def mode(self) -> str:
        return self._mode

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        tokens = tokenize(query)
        if not tokens:
            return []
        bm25_scores = self._bm25.get_scores(tokens)
        bm25_ranking = sorted(
            range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True
        )
        if self._mode != "hybrid":
            return [
                self._result(i, float(bm25_scores[i])) for i in bm25_ranking[:top_k]
            ]

        assert self._embedder is not None and self._vectors is not None
        query_vec = _normalize(self._embedder([query]))[0]
        sims = self._vectors @ query_vec
        dense_ranking = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)
        # Fuse candidate pools, not full rankings: past the pool BM25 scores are
        # mostly zero ties, which would add rank noise to the fusion.
        pool = max(top_k * 10, 50)
        fused = rrf_fuse([bm25_ranking[:pool], dense_ranking[:pool]])
        ranked = sorted(fused, key=lambda i: fused[i], reverse=True)
        return [self._result(i, fused[i]) for i in ranked[:top_k]]

    def _result(self, chunk_idx: int, score: float) -> SearchResult:
        c = self._chunks[chunk_idx]
        return SearchResult(
            text=c.text,
            score=round(score, 4),
            doc_id=c.doc_id,
            position=c.position,
            title=c.title,
            url=c.url,
            date=c.date,
        )
