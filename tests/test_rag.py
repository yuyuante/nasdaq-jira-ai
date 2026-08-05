from pathlib import Path

import pytest

from nasdaq_jira.config import RagConfig
from nasdaq_jira.models import JiraIssue
from nasdaq_jira.rag.chunking import chunk_issue
from nasdaq_jira.rag.engine import RagEngine
from nasdaq_jira.rag.models import RagAnswer
from nasdaq_jira.rag.prompt import PromptBuilder
from nasdaq_jira.rag.providers import AnswerProvider, EmbeddingProvider
from nasdaq_jira.rag.vector_store import SQLiteFts5VectorStore


class FakeEmbedding(EmbeddingProvider):
    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[float(len(text))] for text in texts]


class FakeAnswer(AnswerProvider):
    async def answer(self, prompt: str) -> RagAnswer:
        return RagAnswer(executive_summary=prompt[:10], technical_summary="details", confidence=0.9, sources=["TEST-1"])


def test_chunking_preserves_issue_key() -> None:
    chunks = chunk_issue(JiraIssue(key="TEST-1", summary="A long summary"), 5, 1)
    assert chunks
    assert all(chunk["issue_key"] == "TEST-1" for chunk in chunks)


def test_prompt_deduplicates_chunks() -> None:
    from nasdaq_jira.rag.models import SearchResult

    result = SearchResult(chunk_id="same", issue_key="TEST-1", text="context", score=1)
    prompt = PromptBuilder().build("question", [result, result])
    assert prompt.count("context") == 1


@pytest.mark.asyncio
async def test_rag_cache_retrieval_and_answer(tmp_path: Path) -> None:
    embeddings = FakeEmbedding()
    store = SQLiteFts5VectorStore(tmp_path / "rag.sqlite3")
    engine = RagEngine(RagConfig(score_threshold=0), embeddings, store, FakeAnswer())
    issue = JiraIssue(key="TEST-1", summary="FIX Session disconnect", description="network timeout")
    await engine.index([issue])
    await engine.index([issue])
    assert embeddings.calls == 1
    results = engine.semantic_search("FIX Session")
    assert results[0].issue_key == "TEST-1"
    answer = await engine.ask("Why did FIX Session disconnect?")
    assert answer.confidence == 0.9
    store.close()