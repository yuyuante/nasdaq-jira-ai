"""Synchronization state and metrics."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SyncState:
    datasource: str
    last_sync_time: datetime | None
    last_issue_id: str | None
    status: str
    updated_at: datetime


@dataclass(slots=True)
class SyncMetrics:
    total_issues: int = 0
    updated_issues: int = 0
    new_issues: int = 0
    skipped_issues: int = 0
    failed_issues: int = 0

    def add_batch(self, total: int, new: int, updated: int, skipped: int) -> None:
        self.total_issues += total
        self.new_issues += new
        self.updated_issues += updated
        self.skipped_issues += skipped
