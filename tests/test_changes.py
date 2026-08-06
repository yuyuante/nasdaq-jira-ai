from pathlib import Path

from nasdaq_jira.changes import ChangeReport
from nasdaq_jira.models import JiraComment, JiraIssue
from nasdaq_jira.storage import SQLiteIssueRepository


def test_change_report_identifies_new_updated_and_unchanged(tmp_path: Path) -> None:
    with SQLiteIssueRepository(tmp_path / "issues.sqlite3") as repository:
        original = JiraIssue(key="NAS-1", summary="Original")
        repository.upsert_many([original])
        report = ChangeReport.from_repository(
            repository,
            [
                original,
                JiraIssue(key="NAS-1", summary="Changed", status="Done"),
                JiraIssue(key="NAS-2", summary="New"),
            ],
        )

    assert [change.change_type for change in report.changes] == [
        "unchanged",
        "updated",
        "new",
    ]
    assert report.updated[0].fields == ("summary", "status")


def test_change_report_describes_added_comments() -> None:
    previous = JiraIssue(key="NAS-1", comments=[JiraComment(body="old")])
    current = JiraIssue(
        key="NAS-1",
        comments=[JiraComment(body="old"), JiraComment(body="new")],
    )

    report = ChangeReport.compare(previous, current)

    assert report.change_type == "updated"
    assert report.fields == ("comment +1",)
