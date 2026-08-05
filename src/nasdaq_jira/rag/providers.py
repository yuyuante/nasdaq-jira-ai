"""Embedding and answer provider interfaces."""

import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from .models import RagAnswer

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class AnswerProvider(ABC):
    @abstractmethod
    async def answer(self, prompt: str) -> RagAnswer: ...


class OpenAIProvider(EmbeddingProvider, AnswerProvider):
    """OpenAI provider using configurable embeddings and answer models."""

    def __init__(
        self, api_key: str, base_url: str, embedding_model: str, answer_model: str
    ) -> None:
        self._embedding_model = embedding_model
        self._answer_model = answer_model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=60,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.post(
            "/embeddings", json={"model": self._embedding_model, "input": texts}
        )
        response.raise_for_status()
        return [
            item["embedding"]
            for item in sorted(response.json()["data"], key=lambda item: item["index"])
        ]

    async def answer(self, prompt: str) -> RagAnswer:
        response = await self._client.post(
            "/chat/completions",
            json={
                "model": self._answer_model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": "Return JSON matching the requested answer schema.",
                    },
                    {"role": "user", "content": prompt},
                ],
            },
        )
        response.raise_for_status()
        content: Any = response.json()["choices"][0]["message"]["content"]
        return RagAnswer.model_validate_json(content)
