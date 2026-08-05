"""RAG indexing, retrieval and answering."""

import logging
import time

from ..config import RagConfig
from ..models import JiraIssue
from .chunking import chunk_issue
from .models import RagAnswer, RagDocument, SearchResult
from .prompt import PromptBuilder
from .providers import AnswerProvider, EmbeddingProvider
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class RagEngine:
    def __init__(
        self,
        config: RagConfig,
        embeddings: EmbeddingProvider,
        store: VectorStore,
        answers: AnswerProvider | None = None,
    ) -> None:
        self._config = config
        self._embeddings = embeddings
        self._store = store
        self._answers = answers
        self._prompts = PromptBuilder()

    async def index(self, issues: list[JiraIssue]) -> int:
        documents: list[RagDocument] = []
        missing: list[dict[str, str]] = []
        for issue in issues:
            for item in chunk_issue(
                issue, self._config.chunk_size, self._config.chunk_overlap
            ):
                document = RagDocument(
                    chunk_id=item["chunk_id"],
                    issue_key=item["issue_key"],
                    text=item["text"],
                    updated_at=item["updated_at"],
                )
                documents.append(document)
                if self._store.embedding_for(document.chunk_id) is None:
                    missing.append(item)
        if missing:
            started = time.perf_counter()
            vectors = await self._embeddings.embed([item["text"] for item in missing])
            logger.info(
                "Embeddings generated count=%d latency=%.3fs",
                len(vectors),
                time.perf_counter() - started,
            )
            by_id = {
                item["chunk_id"]: vector
                for item, vector in zip(missing, vectors, strict=True)
            }
        else:
            by_id = {}
        all_vectors = [
            by_id.get(
                document.chunk_id, self._store.embedding_for(document.chunk_id) or []
            )
            for document in documents
        ]
        self._store.upsert(documents, all_vectors)
        return len(documents)

    def semantic_search(
        self, query: str, filters: dict[str, str] | None = None
    ) -> list[SearchResult]:
        started = time.perf_counter()
        results = self._store.search(
            query, self._config.top_k, self._config.score_threshold, filters
        )
        logger.info(
            "Retrieval latency=%.3fs results=%d",
            time.perf_counter() - started,
            len(results),
        )
        return results

    async def ask(self, query: str, filters: dict[str, str] | None = None) -> RagAnswer:
        if self._answers is None:
            raise RuntimeError("RAG answer provider is not configured")
        results = self.semantic_search(query, filters)
        prompt = self._prompts.build(query, results)
        logger.info("Prompt built chunks=%d prompt_chars=%d", len(results), len(prompt))
        return await self._answers.answer(prompt)
