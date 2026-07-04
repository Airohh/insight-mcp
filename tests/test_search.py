import pytest

from insight_mcp.corpus import Corpus
from insight_mcp.search import EmptyCorpusError, SearchIndex, tokenize


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
