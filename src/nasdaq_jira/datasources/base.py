"""Data source contract used by the application layer."""

from abc import ABC, abstractmethod

from ..models import JiraAttachment, JiraComment, JiraIssue


class JiraDataSource(ABC):
    """Retrieve Jira data without exposing the transport implementation."""

    @abstractmethod
    async def get_issue(self, issue_key: str) -> JiraIssue:
        """Return one issue."""

    @abstractmethod
    async def search_issues(self, jql: str) -> list[JiraIssue]:
        """Search issues with JQL."""

    @abstractmethod
    async def get_comments(self, issue_key: str) -> list[JiraComment]:
        """Return comments for an issue."""

    @abstractmethod
    async def get_attachments(self, issue_key: str) -> list[JiraAttachment]:
        """Return attachments for an issue."""
