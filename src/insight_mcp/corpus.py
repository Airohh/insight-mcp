"""SQLite storage for ingested documents and their search chunks.

Documents keep the full extracted text (served by `get_publication`); chunks
are the overlapping windows the BM25 index scores (overlap means joining them
back would duplicate text, hence the separate full-text column).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    date TEXT,
    text TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    doc_id INTEGER NOT NULL REFERENCES documents(id),
    position INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
"""


@dataclass(frozen=True)
class Document:
    id: int
    url: str
    title: str
    date: str | None


@dataclass(frozen=True)
class IndexedChunk:
    """A chunk joined with its source document, ready for indexing."""

    chunk_id: int
    doc_id: int
    position: int
    text: str
    title: str
    url: str
    date: str | None


class Corpus:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def upsert_document(
        self,
        url: str,
        title: str,
        date: str | None,
        text: str,
        chunks: list[str],
        fetched_at: str,
    ) -> int:
        """Insert a document, replacing any previous version of the same URL."""
        with self._conn:
            row = self._conn.execute(
                "SELECT id FROM documents WHERE url = ?", (url,)
            ).fetchone()
            if row:
                doc_id = row["id"]
                self._conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
                self._conn.execute(
                    "UPDATE documents SET title = ?, date = ?, text = ?, fetched_at = ?"
                    " WHERE id = ?",
                    (title, date, text, fetched_at, doc_id),
                )
            else:
                cur = self._conn.execute(
                    "INSERT INTO documents (url, title, date, text, fetched_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (url, title, date, text, fetched_at),
                )
                doc_id = cur.lastrowid
            self._conn.executemany(
                "INSERT INTO chunks (doc_id, position, text) VALUES (?, ?, ?)",
                [(doc_id, i, chunk) for i, chunk in enumerate(chunks)],
            )
        return doc_id

    def documents(self) -> list[Document]:
        rows = self._conn.execute(
            "SELECT id, url, title, date FROM documents ORDER BY date DESC, id"
        ).fetchall()
        return [Document(r["id"], r["url"], r["title"], r["date"]) for r in rows]

    def get_document(self, doc_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT id, url, title, date, text, fetched_at FROM documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
        return dict(row) if row else None

    def indexed_chunks(self) -> list[IndexedChunk]:
        rows = self._conn.execute(
            "SELECT c.id, c.doc_id, c.position, c.text, d.title, d.url, d.date"
            " FROM chunks c JOIN documents d ON d.id = c.doc_id ORDER BY c.id"
        ).fetchall()
        return [
            IndexedChunk(
                chunk_id=r["id"],
                doc_id=r["doc_id"],
                position=r["position"],
                text=r["text"],
                title=r["title"],
                url=r["url"],
                date=r["date"],
            )
            for r in rows
        ]

    def stats(self) -> dict[str, int]:
        docs = self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunks = self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {"documents": docs, "chunks": chunks}
