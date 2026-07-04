import numpy as np
import pytest

from insight_mcp.corpus import Corpus
from insight_mcp.search import EmptyCorpusError, SearchIndex, rrf_fuse, tokenize


def test_tokenize_lowercases_and_splits():
    assert tokenize("L'IA générative, en Entreprise!") == [
        "l", "ia", "générative", "en", "entreprise",
    ]


def test_search_ranks_relevant_doc_first(corpus):
    index = SearchIndex(corpus)
    results = index.search("ransomware zero-trust security")
    assert results
    assert results[0].title == "Cybersecurity radar 2026"
    assert results[0].url == "https://example.com/cyber-radar"
    assert results[0].score > 0


def test_search_respects_top_k(corpus):
    index = SearchIndex(corpus)
    assert len(index.search("cloud", top_k=2)) == 2


def test_search_empty_query_returns_nothing(corpus):
    index = SearchIndex(corpus)
    assert index.search("   !!!   ") == []


def test_empty_corpus_raises(tmp_path):
    empty = Corpus(tmp_path / "empty.db")
    with pytest.raises(EmptyCorpusError, match="ingest"):
        SearchIndex(empty)
    empty.close()


# --- hybrid mode (fake embedder: hash-based bag-of-words, no model download) ---


def fake_embedder(texts):
    """Deterministic embeddings: token-hash bag-of-words in 64 dims.

    Crude, but texts sharing words land near each other — enough to exercise
    the dense path and the RRF fusion without downloading a real model.
    """
    vecs = np.zeros((len(texts), 64), dtype=np.float32)
    for row, text in enumerate(texts):
        for token in tokenize(text):
            vecs[row, hash(token) % 64] += 1.0
    return vecs


def test_rrf_fuse_rewards_agreement():
    # doc 0 ranks 1st in both lists; doc 1 and 2 each rank 1st in only one
    scores = rrf_fuse([[0, 1, 2], [0, 2, 1]], k=60)
    assert scores[0] > scores[1]
    assert scores[0] > scores[2]


def test_rrf_fuse_handles_disjoint_lists():
    scores = rrf_fuse([[1, 2], [3, 4]])
    assert set(scores) == {1, 2, 3, 4}


def test_hybrid_requires_embedder(corpus):
    with pytest.raises(ValueError, match="embedder"):
        SearchIndex(corpus, mode="hybrid")


def test_hybrid_search_returns_ranked_results(corpus):
    index = SearchIndex(corpus, mode="hybrid", embedder=fake_embedder)
    results = index.search("ransomware zero-trust security", top_k=3)
    assert results
    assert results[0].title == "Cybersecurity radar 2026"
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_hybrid_empty_query_returns_nothing(corpus):
    index = SearchIndex(corpus, mode="hybrid", embedder=fake_embedder)
    assert index.search("???") == []


def test_mode_property(corpus):
    assert SearchIndex(corpus).mode == "bm25"
    assert SearchIndex(corpus, mode="hybrid", embedder=fake_embedder).mode == "hybrid"
