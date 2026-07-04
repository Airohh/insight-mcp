"""Tools tested through their underlying functions, with the module-level
corpus/index swapped for the synthetic fixture (no network, no real data/)."""

import json

import pytest

import insight_mcp.server as server
from insight_mcp.search import SearchIndex


@pytest.fixture()
def wired_server(corpus, monkeypatch):
    monkeypatch.setattr(server, "_corpus", corpus)
    monkeypatch.setattr(server, "_index", SearchIndex(corpus))
    return server


def test_search_publications_returns_sources(wired_server):
    results = wired_server.search_publications("ransomware security", top_k=3)
    assert results
    top = results[0]
    assert {"text", "score", "doc_id", "title", "url", "date"} <= set(top)
    assert top["title"] == "Cybersecurity radar 2026"


def test_search_publications_clamps_top_k(wired_server):
    assert len(wired_server.search_publications("cloud", top_k=9999)) <= server.MAX_TOP_K
    assert len(wired_server.search_publications("cloud", top_k=-5)) == 1


def test_get_publication_full_text(wired_server):
    doc_id = wired_server.search_publications("finops cloud")[0]["doc_id"]
    doc = wired_server.get_publication(doc_id)
    assert doc["title"] == "Cloud FinOps practices"
    assert "financial accountability" in doc["text"]


def test_get_publication_unknown_id(wired_server):
    with pytest.raises(ValueError, match="doc_id=999"):
        wired_server.get_publication(999)


def test_get_publication_truncates_long_text(wired_server, corpus, monkeypatch):
    monkeypatch.setattr(server, "MAX_DOC_CHARS", 50)
    doc_id = corpus.documents()[0].id
    doc = wired_server.get_publication(doc_id)
    assert len(doc["text"]) == 50
    assert doc["text_truncated"] is True


def test_list_topics_overview(wired_server):
    overview = wired_server.list_topics()
    assert overview["documents"] == 3
    assert overview["chunks"] > 0
    titles = {p["title"] for p in overview["publications"]}
    assert "AI agents in the enterprise" in titles


def test_corpus_stats_resource(wired_server):
    stats = json.loads(wired_server.corpus_stats())
    assert stats["documents"] == 3
    assert stats["latest_date"] == "2026-03-02"
    assert stats["oldest_date"] == "2025-11-20"
    assert stats["search_mode"] in ("bm25", "hybrid")


def test_corpus_health_resource_ok(wired_server):
    health = json.loads(wired_server.corpus_health())
    assert health["status"] == "ok"
    assert health["chunks"] > 0


def test_corpus_health_resource_reports_error(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_corpus", None)
    monkeypatch.setattr(server, "_index", None)
    monkeypatch.setattr(
        server, "get_settings", lambda: type(
            "S", (), {"db_path": tmp_path / "nope.db"}
        )()
    )
    health = json.loads(server.corpus_health())
    assert health["status"] == "error"
    assert "ingest" in health["detail"]


def test_grounded_answer_prompt_mentions_tool_and_question(wired_server):
    text = wired_server.grounded_answer("What about AI agents?")
    assert "search_publications" in text
    assert "What about AI agents?" in text


def test_missing_db_message(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_corpus", None)
    monkeypatch.setattr(server, "_index", None)
    monkeypatch.setattr(
        server, "get_settings", lambda: type(
            "S", (), {"db_path": tmp_path / "nope.db"}
        )()
    )
    with pytest.raises(RuntimeError, match="ingest"):
        server.search_publications("anything")
