"""Issue document chunking."""

import hashlib

from ..models import JiraIssue


def issue_text(issue: JiraIssue) -> str:
    parts = [f"Issue {issue.key}: {issue.summary}"]
    for label, value in (
        ("Description", issue.description),
        ("Status", issue.status),
        ("Priority", issue.priority),
        ("Resolution", None),
    ):
        if value:
            parts.append(f"{label}: {value}")
    for comment in issue.comments:
        parts.append(f"Comment: {comment.body}")
    for attachment in issue.attachments:
        parts.append(f"Attachment: {attachment.filename}")
    return "\n".join(parts)


def chunk_issue(
    issue: JiraIssue, chunk_size: int, overlap: int
) -> list[dict[str, str]]:
    text = issue_text(issue)
    step = max(1, chunk_size - overlap)
    return [
        {
            "chunk_id": hashlib.sha256(
                f"{issue.key}:{start}:{text[start : start + chunk_size]}".encode()
            ).hexdigest(),
            "issue_key": issue.key,
            "text": text[start : start + chunk_size],
            "updated_at": issue.updated_at or "",
        }
        for start in range(0, len(text), step)
    ] or [
        {
            "chunk_id": hashlib.sha256(issue.key.encode()).hexdigest(),
            "issue_key": issue.key,
            "text": "",
            "updated_at": issue.updated_at or "",
        }
    ]
