from pathlib import Path

import pytest

from nasdaq_jira.config import SyncConfig
from nasdaq_jira.datasources.base import JiraDataSource
from nasdaq_jira.models import JiraIssue, JiraIssueDetails
from nasdaq_jira.storage import SQLiteIssueRepository
from nasdaq_jira.sync.engine import SyncEngine


class FakeSource(JiraDataSource):
    def __init__(self, issues: list[JiraIssue]) -> None:
        self.issues = issues
        self.queries: list[str] = []

    async def get_issue(self, issue_key: str) -> JiraIssue:
        return next(issue for issue in self.issues if issue.key == issue_key)

    async def search_issues(self, jql: str) -> list[JiraIssue]:
        self.queries.append(jql)
        return self.issues

    async def get_comments(self, issue_key: str) -> list[object]:
        return []

    async def get_attachments(self, issue_key: str) -> list[object]:
        return []


def issue(
    key: str, summary: str = "summary", created_at: str | None = None
) -> JiraIssue:
    return JiraIssue(
        key=key,
        summary=summary,
        updated_at="2026-08-05T00:00:00+00:00",
        details=JiraIssueDetails(created_at=created_at),
    )


def engine(tmp_path: Path, source: FakeSource, batch_size: int = 50) -> SyncEngine:
    repository = SQLiteIssueRepository(tmp_path / "issues.sqlite3")
    return SyncEngine(
        source, repository, SyncConfig(batch_size=batch_size), "project = TEST"
    )


@pytest.mark.asyncio
async def test_first_sync_and_idempotency(tmp_path: Path) -> None:
    source = FakeSource([issue("TEST-1"), issue("TEST-2")])
    sync = engine(tmp_path, source)
    metrics = await sync.full_sync()
    assert metrics.new_issues == 2
    second = await sync.full_sync()
    assert second.skipped_issues == 2


@pytest.mark.asyncio
async def test_sync_preserves_created_at_when_source_omits_it(tmp_path: Path) -> None:
    source = FakeSource([issue("TEST-1", created_at="2026-08-05 09:00")])
    sync = engine(tmp_path, source)
    await sync.full_sync()

    source.issues = [issue("TEST-1")]
    await sync.full_sync()

    stored = sync._repository.get_issue("TEST-1")
    assert stored is not None
    assert stored.details.created_at == "2026-08-05 09:00"


@pytest.mark.asyncio
async def test_incremental_query_uses_six_hour_overlap(tmp_path: Path) -> None:
    source = FakeSource([issue("TEST-1")])
    sync = engine(tmp_path, source)
    await sync.full_sync()
    await sync.incremental_sync()
    assert "updated >=" in source.queries[-1]


@pytest.mark.asyncio
async def test_resume_uses_checkpoint(tmp_path: Path) -> None:
    source = FakeSource([issue("TEST-1"), issue("TEST-2")])
    sync = engine(tmp_path, source, batch_size=1)
    original = sync._process_batch
    calls = 0

    def interrupted(batch: list[JiraIssue]) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("interrupted")
        original(batch)

    sync._process_batch = interrupted  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await sync.full_sync()
    sync._process_batch = original  # type: ignore[method-assign]
    metrics = await sync.resume_sync()
    assert metrics.new_issues == 1
