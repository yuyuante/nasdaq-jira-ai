from nasdaq_jira.models import JiraComment
from nasdaq_jira.parser import is_valid_jira_issue_key, summarize_comments


def test_is_valid_jira_issue_key_rejects_navigation_text() -> None:
    assert is_valid_jira_issue_key("XTAIFEX-307")
    assert not is_valid_jira_issue_key("Activity")
    assert not is_valid_jira_issue_key("2026")


def test_summarize_comments_includes_each_comment() -> None:
    comments = [
        JiraComment(body="First investigation result."),
        JiraComment(body="Second investigation result."),
    ]

    summary = summarize_comments(comments)

    assert "1. First investigation result." in summary
    assert "2. Second investigation result." in summary
