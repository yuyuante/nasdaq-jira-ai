from nasdaq_jira.parser import is_valid_jira_issue_key


def test_is_valid_jira_issue_key_rejects_navigation_text() -> None:
    assert is_valid_jira_issue_key("XTAIFEX-307")
    assert not is_valid_jira_issue_key("Activity")
    assert not is_valid_jira_issue_key("2026")
