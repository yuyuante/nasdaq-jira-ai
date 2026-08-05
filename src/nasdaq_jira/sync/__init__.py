"""Synchronization services."""

__all__ = [
    "AttachmentAdded",
    "CommentAdded",
    "CommentUpdated",
    "IssueCreated",
    "IssueUpdated",
    "StatusChanged",
    "SyncEngine",
]


def __getattr__(name: str) -> object:
    if name == "SyncEngine":
        from .engine import SyncEngine

        return SyncEngine
    if name in {
        "AttachmentAdded",
        "CommentAdded",
        "CommentUpdated",
        "IssueCreated",
        "IssueUpdated",
        "StatusChanged",
    }:
        from . import events

        return getattr(events, name)
    raise AttributeError(name)
