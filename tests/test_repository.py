from pathlib import Path

from nasdaq_jira.models import JiraIssue
from nasdaq_jira.storage import SQLiteIssueRepository


def test_upsert_is_idempotent(tmp_path: Path) -> None:
    with SQLiteIssueRepository(tmp_path / "issues.sqlite3") as repository:
        issue = JiraIssue("NAS-1", "Initial", "Open")
        assert repository.upsert_many([issue]) == 1
        assert repository.upsert_many([JiraIssue("NAS-1", "Updated", "Done")]) == 1
        assert repository.count() == 1
