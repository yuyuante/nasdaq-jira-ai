"""SQLite repository for normalized Jira issues."""

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .models import JiraIssue


class SQLiteIssueRepository:
    """Persist Jira issues with idempotent upserts."""

    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(database_path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS jira_issues (
                key TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                status TEXT,
                updated_at TEXT,
                source_url TEXT,
                crawled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        self._connection.commit()

    def upsert_many(self, issues: Iterable[JiraIssue]) -> int:
        rows = list(issues)
        self._connection.executemany(
            """INSERT INTO jira_issues(key, summary, status, updated_at, source_url)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                 summary=excluded.summary, status=excluded.status,
                 updated_at=excluded.updated_at, source_url=excluded.source_url,
                 crawled_at=CURRENT_TIMESTAMP""",
            [(i.key, i.summary, i.status, i.updated_at, i.source_url) for i in rows],
        )
        self._connection.commit()
        return len(rows)

    def count(self) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) AS count FROM jira_issues"
        ).fetchone()
        return int(row["count"])

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "SQLiteIssueRepository":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
