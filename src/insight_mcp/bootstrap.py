"""First-run bootstrap: seed the corpus database from the bundled sample docs.

Makes a fresh clone usable immediately (clone → install → connect a client)
while keeping real corpora explicit: running scripts/ingest.py replaces the
sample with downloaded content.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from insight_mcp.corpus import Corpus
from insight_mcp.ingest import chunk_text
from insight_mcp.sample_corpus import SAMPLE_DOCS

log = logging.getLogger(__name__)


def seed_sample_corpus(db_path: Path) -> Corpus:
    """Create the database at db_path and fill it with the sample docs."""
    corpus = Corpus(db_path)
    fetched_at = datetime.now(UTC).isoformat()
    for doc in SAMPLE_DOCS:
        corpus.upsert_document(
            url=doc["url"],
            title=doc["title"],
            date=doc["date"],
            text=doc["text"],
            chunks=chunk_text(doc["text"]),
            fetched_at=fetched_at,
        )
    log.warning(
        "sample_corpus_seeded",
        extra={
            "documents": len(SAMPLE_DOCS),
            "hint": "run 'python scripts/ingest.py' to index a real corpus",
        },
    )
    return corpus
