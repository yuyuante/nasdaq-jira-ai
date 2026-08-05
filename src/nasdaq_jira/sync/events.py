"""Immutable synchronization events."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SyncEvent(BaseModel):
    """Immutable event emitted by synchronization."""

    model_config = ConfigDict(frozen=True)
    event_id: str
    issue_key: str
    occurred_at: datetime
    event_type: str = ""


class IssueCreated(SyncEvent):
    event_type: Literal["IssueCreated"] = "IssueCreated"


class IssueUpdated(SyncEvent):
    event_type: Literal["IssueUpdated"] = "IssueUpdated"


class CommentAdded(SyncEvent):
    event_type: Literal["CommentAdded"] = "CommentAdded"


class CommentUpdated(SyncEvent):
    event_type: Literal["CommentUpdated"] = "CommentUpdated"


class AttachmentAdded(SyncEvent):
    event_type: Literal["AttachmentAdded"] = "AttachmentAdded"


class StatusChanged(SyncEvent):
    event_type: Literal["StatusChanged"] = "StatusChanged"
