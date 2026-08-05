from pathlib import Path

from nasdaq_jira.models import JiraComment, JiraHistoryEntry, JiraIssue
from nasdaq_jira.storage import SQLiteIssueRepository


def test_upsert_is_idempotent(tmp_path: Path) -> None:
    with SQLiteIssueRepository(tmp_path / "issues.sqlite3") as repository:
        issue = JiraIssue(key="NAS-1", summary="Initial", status="Open")
        assert repository.upsert_many([issue]) == 1
        assert (
            repository.upsert_many(
                [JiraIssue(key="NAS-1", summary="Updated", status="Done")]
            )
            == 1
        )
        assert repository.count() == 1


def test_upsert_persists_comments_and_history(tmp_path: Path) -> None:
    with SQLiteIssueRepository(tmp_path / "issues.sqlite3") as repository:
        issue = JiraIssue(
            key="NAS-2",
            summary="With activity",
            comments=[
                JiraComment(
                    comment_id="c1",
                    body="Investigated",
                    summary="Investigation started",
                )
            ],
            history=[JiraHistoryEntry(history_id="h1", details="Status changed")],
        )
        repository.upsert_many([issue])
        stored = repository.get_issue("NAS-2")

    assert stored is not None
    assert stored.comments[0].summary == "Investigation started"
    assert stored.history[0].details == "Status changed"
