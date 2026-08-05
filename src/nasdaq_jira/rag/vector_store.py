"""Vector store abstractions and SQLite FTS5 backend."""

import json
import re
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path

from .models import RagDocument, SearchResult


class VectorStore(ABC):
    @abstractmethod
    def upsert(
        self, documents: list[RagDocument], embeddings: list[list[float]]
    ) -> None: ...

    @abstractmethod
    def embedding_for(self, chunk_id: str) -> list[float] | None: ...

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int,
        threshold: float,
        filters: dict[str, str] | None = None,
    ) -> list[SearchResult]: ...


class SQLiteFts5VectorStore(VectorStore):
    """SQLite FTS5 store with metadata and embedding cache."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS rag_chunks (
                chunk_id TEXT PRIMARY KEY,
                issue_key TEXT NOT NULL,
                text TEXT NOT NULL,
                updated_at TEXT,
                metadata_json TEXT NOT NULL,
                embedding_json TEXT NOT NULL
            )"""
        )
        self._db.execute(
            """CREATE VIRTUAL TABLE IF NOT EXISTS rag_fts
            USING fts5(chunk_id UNINDEXED, text)"""
        )
        self._db.commit()

    def upsert(
        self, documents: list[RagDocument], embeddings: list[list[float]]
    ) -> None:
        for document, embedding in zip(documents, embeddings, strict=True):
            self._db.execute(
                "INSERT OR REPLACE INTO rag_chunks VALUES (?, ?, ?, ?, ?, ?)",
                (
                    document.chunk_id,
                    document.issue_key,
                    document.text,
                    document.updated_at,
                    json.dumps(document.metadata),
                    json.dumps(embedding),
                ),
            )
            self._db.execute(
                "DELETE FROM rag_fts WHERE chunk_id = ?", (document.chunk_id,)
            )
            self._db.execute(
                "INSERT INTO rag_fts(chunk_id, text) VALUES (?, ?)",
                (document.chunk_id, document.text),
            )
        self._db.commit()

    def embedding_for(self, chunk_id: str) -> list[float] | None:
        row = self._db.execute(
            "SELECT embedding_json FROM rag_chunks WHERE chunk_id = ?", (chunk_id,)
        ).fetchone()
        return json.loads(row["embedding_json"]) if row else None

    def search(
        self,
        query: str,
        top_k: int,
        threshold: float,
        filters: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        rows = self._db.execute(
            """SELECT c.*, bm25(rag_fts) AS rank
            FROM rag_fts JOIN rag_chunks c ON c.chunk_id = rag_fts.chunk_id
            WHERE rag_fts MATCH ? ORDER BY rank LIMIT ?""",
            (self._fts_query(query), top_k * 5),
        ).fetchall()
        results = []
        for row in rows:
            metadata = json.loads(row["metadata_json"])
            if filters and any(
                metadata.get(key) != value for key, value in filters.items()
            ):
                continue
            score = 1 / (1 + max(0.0, float(row["rank"])))
            if score >= threshold:
                results.append(
                    SearchResult(
                        chunk_id=row["chunk_id"],
                        issue_key=row["issue_key"],
                        text=row["text"],
                        score=score,
                        updated_at=row["updated_at"],
                        metadata=metadata,
                    )
                )
        return results[:top_k]

    @staticmethod
    def _fts_query(query: str) -> str:
        terms = re.findall(r"[A-Za-z0-9_]+", query)
        return " OR ".join(f'"{term}"' for term in terms) or '""'

    def close(self) -> None:
        self._db.close()
