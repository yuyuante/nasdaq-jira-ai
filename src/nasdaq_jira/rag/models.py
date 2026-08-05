"""RAG domain models."""

from pydantic import BaseModel, ConfigDict, Field


class SearchResult(BaseModel):
    chunk_id: str
    issue_key: str
    text: str
    score: float
    updated_at: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class RagAnswer(BaseModel):
    executive_summary: str
    technical_summary: str
    action_items: list[str] = Field(default_factory=list)
    related_issues: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    sources: list[str] = Field(default_factory=list)


class RagDocument(BaseModel):
    model_config = ConfigDict(frozen=True)
    chunk_id: str
    issue_key: str
    text: str
    updated_at: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
