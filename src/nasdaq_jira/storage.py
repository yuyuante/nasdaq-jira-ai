"""SQLite persistence for issues, synchronization state and events."""

import hashlib
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from .models import JiraIssue
from .sync.events import SyncEvent
from .sync.state import SyncState


class SQLiteIssueRepository:
    """Persist Jira snapshots idempotently with synchronization checkpoints."""

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
                crawled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                issue_json TEXT
            )"""
        )
        columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(jira_issues)")
        }
        if "issue_json" not in columns:
            self._connection.execute(
                "ALTER TABLE jira_issues ADD COLUMN issue_json TEXT"
            )
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS jira_comments (
                issue_key TEXT NOT NULL,
                comment_id TEXT NOT NULL,
                author TEXT,
                created_at TEXT,
                body TEXT NOT NULL,
                summary TEXT,
                body_hash TEXT NOT NULL,
                PRIMARY KEY(issue_key, comment_id),
                FOREIGN KEY(issue_key) REFERENCES jira_issues(key) ON DELETE CASCADE
            )"""
        )
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS jira_history (
                issue_key TEXT NOT NULL,
                history_id TEXT NOT NULL,
                author TEXT,
                created_at TEXT,
                details TEXT NOT NULL,
                PRIMARY KEY(issue_key, history_id),
                FOREIGN KEY(issue_key) REFERENCES jira_issues(key) ON DELETE CASCADE
            )"""
        )
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS sync_state (
                datasource TEXT PRIMARY KEY,
                last_sync_time TEXT,
                last_issue_id TEXT,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS sync_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                issue_key TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            )"""
        )
        self._connection.commit()

    def upsert_many(self, issues: Iterable[JiraIssue]) -> int:
        """Upsert issues and replace their normalized comments and history."""
        rows = list(issues)
        self._connection.executemany(
            """INSERT INTO jira_issues(
                key, summary, status, updated_at, source_url, issue_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                summary=excluded.summary,
                status=excluded.status,
                updated_at=excluded.updated_at,
                source_url=excluded.source_url,
                issue_json=excluded.issue_json,
                crawled_at=CURRENT_TIMESTAMP""",
            [
                (
                    issue.key,
                    issue.summary,
                    issue.status,
                    issue.updated_at,
                    issue.source_url,
                    issue.model_dump_json(),
                )
                for issue in rows
            ],
        )
        for issue in rows:
            self._connection.execute(
                "DELETE FROM jira_comments WHERE issue_key = ?", (issue.key,)
            )
            self._connection.execute(
                "DELETE FROM jira_history WHERE issue_key = ?", (issue.key,)
            )
            self._connection.executemany(
                """INSERT INTO jira_comments(
                    issue_key, comment_id, author, created_at, body, summary, body_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        issue.key,
                        comment.comment_id or f"comment-{index}",
                        comment.author,
                        comment.created_at,
                        comment.body,
                        comment.summary,
                        hashlib.sha256(comment.body.encode("utf-8")).hexdigest(),
                    )
                    for index, comment in enumerate(issue.comments)
                ],
            )
            self._connection.executemany(
                """INSERT INTO jira_history(
                    issue_key, history_id, author, created_at, details
                ) VALUES (?, ?, ?, ?, ?)""",
                [
                    (
                        issue.key,
                        entry.history_id or f"history-{index}",
                        entry.author,
                        entry.created_at,
                        entry.details,
                    )
                    for index, entry in enumerate(issue.history)
                ],
            )
        self._connection.commit()
        return len(rows)

    def get_issue(self, key: str) -> JiraIssue | None:
        row = self._connection.execute(
            "SELECT * FROM jira_issues WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        if row["issue_json"]:
            return JiraIssue.model_validate_json(row["issue_json"])
        return JiraIssue(
            key=row["key"],
            summary=row["summary"],
            status=row["status"],
            updated_at=row["updated_at"],
            source_url=row["source_url"],
        )

    def insert_events(self, events: Iterable[SyncEvent]) -> int:
        rows = [
            (
                event.event_id,
                event.event_type,
                event.issue_key,
                event.occurred_at.isoformat(),
            )
            for event in events
        ]
        self._connection.executemany(
            """INSERT OR IGNORE INTO sync_events(
                event_id, event_type, issue_key, occurred_at
            ) VALUES (?, ?, ?, ?)""",
            rows,
        )
        self._connection.commit()
        return len(rows)

    def get_sync_state(self, datasource: str) -> SyncState | None:
        row = self._connection.execute(
            "SELECT * FROM sync_state WHERE datasource = ?", (datasource,)
        ).fetchone()
        if row is None:
            return None
        return SyncState(
            datasource=row["datasource"],
            last_sync_time=(
                datetime.fromisoformat(row["last_sync_time"])
                if row["last_sync_time"]
                else None
            ),
            last_issue_id=row["last_issue_id"],
            status=row["status"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def set_sync_state(
        self,
        datasource: str,
        last_sync_time: datetime | None,
        last_issue_id: str | None,
        status: str,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        self._connection.execute(
            """INSERT INTO sync_state(
                datasource, last_sync_time, last_issue_id, status, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(datasource) DO UPDATE SET
                last_sync_time=excluded.last_sync_time,
                last_issue_id=excluded.last_issue_id,
                status=excluded.status,
                updated_at=excluded.updated_at""",
            (
                datasource,
                last_sync_time.isoformat() if last_sync_time else None,
                last_issue_id,
                status,
                now,
            ),
        )
        self._connection.commit()

    def all_issues(self) -> list[JiraIssue]:
        rows = self._connection.execute("SELECT key FROM jira_issues").fetchall()
        issues: list[JiraIssue] = []
        for row in rows:
            issue = self.get_issue(row["key"])
            if issue is not None:
                issues.append(issue)
        return issues

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
