"""Validated Jira domain models."""

from pydantic import BaseModel, Field


class JiraIssueDetails(BaseModel):
    """Additional fields shown in a Jira issue's Details panel."""

    issue_type: str | None = None
    resolution: str | None = None
    affects_versions: list[str] = Field(default_factory=list)
    service_product: str | None = None
    created_at: str | None = None


class JiraComment(BaseModel):
    """A Jira issue comment."""

    comment_id: str | None = None
    body: str
    summary: str | None = None
    author: str | None = None
    created_at: str | None = None


class JiraAttachment(BaseModel):
    """A Jira issue attachment."""

    filename: str
    url: str | None = None


class JiraHistoryChange(BaseModel):
    """One field change recorded in Jira history."""

    field: str
    old_value: str | None = None
    new_value: str | None = None


class JiraHistoryEntry(BaseModel):
    """A Jira issue history entry."""

    history_id: str | None = None
    details: str
    author: str | None = None
    created_at: str | None = None
    changes: list[JiraHistoryChange] = Field(default_factory=list)


class JiraIssue(BaseModel):
    """A normalized Jira issue suitable for persistence and export."""

    key: str = Field(min_length=1)
    summary: str = ""
    status: str | None = None
    priority: str | None = None
    description: str | None = None
    assignee: str | None = None
    reporter: str | None = None
    labels: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    fix_versions: list[str] = Field(default_factory=list)
    comments: list[JiraComment] = Field(default_factory=list)
    attachments: list[JiraAttachment] = Field(default_factory=list)
    history: list[JiraHistoryEntry] = Field(default_factory=list)
    updated_at: str | None = None
    source_url: str | None = None
    details: JiraIssueDetails = Field(default_factory=JiraIssueDetails)
    resolution_summary: str | None = None
