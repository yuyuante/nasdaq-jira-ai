"""Domain models."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JiraIssue:
    """A normalized Jira issue suitable for persistence."""

    key: str
    summary: str
    status: str | None = None
    updated_at: str | None = None
    source_url: str | None = None
