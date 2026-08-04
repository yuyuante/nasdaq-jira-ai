"""Validated Jira domain models."""

from pydantic import BaseModel, Field


class JiraComment(BaseModel):
    """A Jira issue comment."""

    body: str
    author: str | None = None
    created_at: str | None = None


class JiraAttachment(BaseModel):
    """A Jira issue attachment."""

    filename: str
    url: str | None = None


class JiraHistoryEntry(BaseModel):
    """A Jira issue history entry."""

    details: str
    author: str | None = None
    created_at: str | None = None


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
