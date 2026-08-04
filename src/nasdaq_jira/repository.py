"""Repository interfaces for Jira issue persistence."""

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from .models import JiraIssue


class IssueRepository(Protocol):
    """Persistence contract used by the application service layer."""

    def upsert_many(self, issues: Iterable[JiraIssue]) -> int:
        """Insert or update a collection of issues."""
        ...

    def count(self) -> int:
        """Return the number of persisted issues."""
        ...

    def close(self) -> None:
        """Release persistence resources."""
        ...


class RepositoryFactory(Protocol):
    """Factory contract for creating an issue repository."""

    def __call__(self, database_path: Path) -> IssueRepository: ...
