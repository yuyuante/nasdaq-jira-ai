"""Incremental Jira synchronization engine."""

import hashlib
import logging
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from ..changes import ChangeReport
from ..config import SyncConfig
from ..datasources.base import JiraDataSource
from ..models import JiraIssue
from ..storage import SQLiteIssueRepository
from .events import (
    AttachmentAdded,
    CommentAdded,
    CommentUpdated,
    IssueCreated,
    IssueUpdated,
    StatusChanged,
    SyncEvent,
)
from .state import SyncMetrics

logger = logging.getLogger(__name__)


class SyncEngine:
    """Synchronize Jira snapshots in idempotent batches."""

    def __init__(
        self,
        datasource: JiraDataSource,
        repository: SQLiteIssueRepository,
        config: SyncConfig,
        jql: str,
    ) -> None:
        self._datasource = datasource
        self._repository = repository
        self._config = config
        self._jql = jql
        self.metrics = SyncMetrics()
        self.report = ChangeReport()

    async def full_sync(self) -> SyncMetrics:
        return await self._run("full")

    async def incremental_sync(self) -> SyncMetrics:
        return await self._run("incremental")

    async def resume_sync(self) -> SyncMetrics:
        return await self._run("resume")

    async def _run(self, mode: str) -> SyncMetrics:
        self.metrics = SyncMetrics()
        self.report = ChangeReport()
        started = time.perf_counter()
        state = self._repository.get_sync_state(self._config.datasource)
        if mode == "resume" and state and state.status == "running":
            last_time = state.last_sync_time
        elif mode == "incremental" and state and state.last_sync_time:
            last_time = state.last_sync_time
        else:
            last_time = None
        query = self._jql
        if last_time is not None:
            overlap = last_time - timedelta(hours=self._config.overlap_hours)
            query = f'({query}) AND updated >= "{overlap.isoformat()}"'
        self._repository.set_sync_state(
            self._config.datasource, last_time, None, "running"
        )
        logger.info("Sync started mode=%s batch_size=%d", mode, self._config.batch_size)
        try:
            issues = await self._datasource.search_issues(query)
            if mode == "resume" and state and state.last_issue_id:
                issues = self._after_checkpoint(issues, state.last_issue_id)
            for offset in range(0, len(issues), self._config.batch_size):
                batch = issues[offset : offset + self._config.batch_size]
                self._process_batch(batch)
                last = batch[-1]
                self._repository.set_sync_state(
                    self._config.datasource, datetime.now(UTC), last.key, "running"
                )
                logger.info("Sync checkpoint issue=%s batch=%d", last.key, len(batch))
            now = datetime.now(UTC)
            self._repository.set_sync_state(
                self._config.datasource, now, None, "completed"
            )
            logger.info(
                "Sync completed duration=%.3fs issues=%d",
                time.perf_counter() - started,
                self.metrics.total_issues,
            )
            return self.metrics
        except Exception:
            self.metrics.failed_issues += 1
            self._repository.set_sync_state(
                self._config.datasource,
                datetime.now(UTC),
                state.last_issue_id if state else None,
                "failed",
            )
            logger.exception("Sync failed")
            raise

    def _process_batch(self, issues: list[JiraIssue]) -> None:
        report = ChangeReport.from_repository(self._repository, issues)
        events: list[SyncEvent] = []
        self.report.changes.extend(report.changes)
        for issue, change in zip(issues, report.changes, strict=True):
            if change.change_type == "new":
                events.append(self._event(IssueCreated, issue.key))
            elif change.change_type == "unchanged":
                continue
            else:
                events.append(self._event(IssueUpdated, issue.key))
                if "status" in change.fields:
                    events.append(self._event(StatusChanged, issue.key))
                if any(field.startswith("comment +") for field in change.fields):
                    events.append(self._event(CommentAdded, issue.key))
                elif "comment" in change.fields:
                    events.append(self._event(CommentUpdated, issue.key))
                if any(field.startswith("attachment +") for field in change.fields):
                    events.append(self._event(AttachmentAdded, issue.key))
        self._repository.upsert_many(issues)
        self._repository.insert_events(events)
        self.metrics.add_batch(
            len(issues), len(report.new), len(report.updated), len(report.unchanged)
        )

    @staticmethod
    def _event(event_type: type[SyncEvent], issue_key: str) -> SyncEvent:
        event_id = hashlib.sha256(
            f"{event_type.__name__}:{issue_key}".encode()
        ).hexdigest()
        return event_type(
            event_id=event_id, issue_key=issue_key, occurred_at=datetime.now(UTC)
        )

    @staticmethod
    def _after_checkpoint(issues: list[JiraIssue], checkpoint: str) -> list[JiraIssue]:
        for index, issue in enumerate(issues):
            if issue.key == checkpoint:
                return issues[index + 1 :]
        return issues


def jql_from_search_url(search_url: str) -> str:
    """Extract JQL from the configured search URL."""
    return parse_qs(urlparse(search_url).query).get("jql", [""])[0]
