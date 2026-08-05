from nasdaq_jira.models import JiraAttachment, JiraComment, JiraHistoryEntry, JiraIssue


def test_issue_model_contains_complete_jira_fields() -> None:
    issue = JiraIssue(
        key="NAS-1",
        summary="Example",
        priority="High",
        labels=["bug"],
        components=["API"],
        fix_versions=["1.0"],
        comments=[JiraComment(body="Needs review")],
        attachments=[JiraAttachment(filename="log.txt")],
        history=[JiraHistoryEntry(details="Status changed")],
    )

    assert issue.key == "NAS-1"
    assert issue.comments[0].body == "Needs review"
    assert issue.attachments[0].filename == "log.txt"
    assert issue.history[0].details == "Status changed"
