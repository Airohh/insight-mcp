"""Shared fixtures: a small synthetic corpus, no network anywhere."""

from __future__ import annotations

import pytest

from insight_mcp.corpus import Corpus
from insight_mcp.ingest import chunk_text

DOCS = [
    {
        "url": "https://example.com/ai-agents",
        "title": "AI agents in the enterprise",
        "date": "2026-01-15",
        "text": (
            "Autonomous AI agents are transforming enterprise workflows."
            " Orchestration frameworks coordinate multiple agents through"
            " protocols such as MCP. Governance and monitoring remain the"
            " main adoption blockers for large organizations."
        ),
    },
    {
        "url": "https://example.com/cyber-radar",
        "title": "Cybersecurity radar 2026",
        "date": "2026-03-02",
        "text": (
            "Ransomware attacks keep rising across critical infrastructure."
            " Zero-trust architectures and identity management dominate"
            " security investments. Incident response maturity varies widely"
            " between sectors."
        ),
    },
    {
        "url": "https://example.com/cloud-finops",
        "title": "Cloud FinOps practices",
        "date": "2025-11-20",
        "text": (
            "FinOps teams bring financial accountability to cloud spending."
            " Tagging discipline and showback dashboards reduce waste."
            " Reserved capacity planning cuts compute costs significantly."
        ),
    },
]


@pytest.fixture()
def corpus(tmp_path) -> Corpus:
    c = Corpus(tmp_path / "corpus.db")
    for doc in DOCS:
        c.upsert_document(
            url=doc["url"],
            title=doc["title"],
            date=doc["date"],
            text=doc["text"],
            chunks=chunk_text(doc["text"], size=20, overlap=5),
            fetched_at="2026-07-04T00:00:00+00:00",
        )
    yield c
    c.close()
