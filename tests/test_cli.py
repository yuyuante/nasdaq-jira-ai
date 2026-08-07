from nasdaq_jira.changes import ChangeReport, IssueChange
from nasdaq_jira.cli import _format_issue, format_change_report
from nasdaq_jira.models import JiraComment, JiraIssue


def test_format_issue_defaults_to_comment_summary() -> None:
    issue = JiraIssue(
        key="XTAIFEX-306",
        summary="No time issue",
        status="Under Investigation",
        description="Investigating the production behavior.",
        resolution_summary="Combined comments summary.",
        comments=[
            JiraComment(
                comment_id="c1",
                author="Peter Yu",
                created_at="2026-08-05 09:00",
                body="The raw comment body.",
                summary="The summarized comment.",
            )
        ],
    )

    output = _format_issue(issue)

    assert "XTAIFEX-306" in output
    assert "Under Investigation" in output
    assert "Investigating the production behavior." in output
    assert "Comments count: 1" in output
    assert "Comments summary:" in output
    assert "Combined comments summary." in output
    assert "The raw comment body." not in output


def test_format_issue_can_include_all_comments() -> None:
    issue = JiraIssue(
        key="XTAIFEX-306",
        resolution_summary="Combined comments summary.",
        comments=[JiraComment(body="The raw comment body.", summary="Short summary")],
    )

    output = _format_issue(issue, all_comments=True)

    assert "All comments:" in output
    assert "The raw comment body." in output


def test_format_change_report_lists_new_and_updated_issues() -> None:
    report = ChangeReport(
        changes=[
            IssueChange("NAS-1", "new"),
            IssueChange(
                "NAS-2",
                "updated",
                ("status", "comment +1"),
                (("status", "Open", "Done"), ("comment", "1", "2")),
            ),
            IssueChange("NAS-3", "unchanged"),
        ]
    )

    output = format_change_report(report)

    assert "- New: 1" in output
    assert "- Updated: 1" in output
    assert "- Unchanged: 1" in output
    assert "- NAS-2: status (Open -> Done), comment (1 -> 2)" in output
