"""Compare Jira snapshots before they are persisted."""

from dataclasses import dataclass, field
from typing import ClassVar

from .models import JiraIssue
from .storage import SQLiteIssueRepository


@dataclass(frozen=True, slots=True)
class IssueChange:
    """The observable changes between two snapshots of one issue."""

    key: str
    change_type: str
    fields: tuple[str, ...] = ()
    differences: tuple[tuple[str, str, str], ...] = ()


@dataclass(slots=True)
class ChangeReport:
    """Aggregate changes found while processing a batch of Jira issues."""

    changes: list[IssueChange] = field(default_factory=list)

    _SCALAR_FIELDS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("summary", "summary"),
        ("status", "status"),
        ("priority", "priority"),
        ("description", "description"),
        ("assignee", "assignee"),
        ("reporter", "reporter"),
        ("labels", "labels"),
        ("components", "components"),
        ("fix_versions", "fix versions"),
        ("updated_at", "updated time"),
        ("details", "details"),
        ("resolution_summary", "resolution summary"),
    )

    @classmethod
    def from_repository(
        cls, repository: SQLiteIssueRepository, issues: list[JiraIssue]
    ) -> "ChangeReport":
        report = cls()
        for issue in issues:
            previous = repository.get_issue(issue.key)
            report.changes.append(cls.compare(previous, issue))
        return report

    @classmethod
    def compare(cls, previous: JiraIssue | None, current: JiraIssue) -> IssueChange:
        if previous is None:
            return IssueChange(current.key, "new")
        if previous.model_dump_json() == current.model_dump_json():
            return IssueChange(current.key, "unchanged")

        fields = []
        differences = []
        for attribute, label in cls._SCALAR_FIELDS:
            before = getattr(previous, attribute)
            after = getattr(current, attribute)
            if before != after:
                fields.append(label)
                differences.append(
                    (label, cls._format_value(before), cls._format_value(after))
                )
        for attribute in ("comments", "attachments", "history"):
            before = getattr(previous, attribute)
            after = getattr(current, attribute)
            if before != after:
                label = attribute[:-1] if attribute.endswith("s") else attribute
                differences.append((label, str(len(before)), str(len(after))))
        fields.extend(cls._activity_change(previous, current, "comments"))
        fields.extend(cls._activity_change(previous, current, "attachments"))
        fields.extend(cls._activity_change(previous, current, "history"))
        return IssueChange(current.key, "updated", tuple(fields), tuple(differences))

    @staticmethod
    def _format_value(value: object) -> str:
        if value is None:
            return "(none)"
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value) or "(empty)"
        formatted = str(value).replace("\r", "").replace("\n", "\\n")
        if len(formatted) > 160:
            return f"{formatted[:157]}..."
        return formatted

    @staticmethod
    def _activity_change(
        previous: JiraIssue, current: JiraIssue, attribute: str
    ) -> list[str]:
        before = getattr(previous, attribute)
        after = getattr(current, attribute)
        if before == after:
            return []
        delta = len(after) - len(before)
        label = attribute[:-1] if attribute.endswith("s") else attribute
        if delta > 0:
            return [f"{label} +{delta}"]
        if delta < 0:
            return [f"{label} {delta}"]
        return [label]

    @property
    def total(self) -> int:
        return len(self.changes)

    @property
    def new(self) -> list[IssueChange]:
        return [change for change in self.changes if change.change_type == "new"]

    @property
    def updated(self) -> list[IssueChange]:
        return [change for change in self.changes if change.change_type == "updated"]

    @property
    def unchanged(self) -> list[IssueChange]:
        return [change for change in self.changes if change.change_type == "unchanged"]
