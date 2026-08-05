"""Jira REST API data source."""

import logging
import time
from typing import Any

import httpx

from ..config import ApiConfig
from ..models import JiraAttachment, JiraComment, JiraIssue
from ..retry import retry_async
from .base import JiraDataSource
from .exceptions import ApiUnavailableError, AuthenticationError, RateLimitError

logger = logging.getLogger(__name__)


class JiraApiDataSource(JiraDataSource):
    """Retrieve Jira issues through REST API v2."""

    def __init__(self, config: ApiConfig) -> None:
        self._config = config
        headers = {"Accept": "application/json"}
        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"
        self._client = httpx.AsyncClient(
            base_url=config.base_url.rstrip("/"),
            headers=headers,
            timeout=config.timeout_ms / 1000,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def health_check(self) -> bool:
        """Check authentication and endpoint availability."""
        try:
            response = await self._request("GET", "/rest/api/2/myself")
        except (AuthenticationError, ApiUnavailableError):
            return False
        return response.status_code == 200

    async def get_issue(self, issue_key: str) -> JiraIssue:
        response = await self._request("GET", f"/rest/api/2/issue/{issue_key}")
        return self._issue_from_json(response.json())

    async def search_issues(self, jql: str) -> list[JiraIssue]:
        issues: list[JiraIssue] = []
        start_at = 0
        while True:
            response = await self._request(
                "GET",
                "/rest/api/2/search",
                params={
                    "jql": jql,
                    "startAt": start_at,
                    "maxResults": self._config.page_size,
                },
            )
            payload = response.json()
            batch = [self._issue_from_json(item) for item in payload.get("issues", [])]
            issues.extend(batch)
            start_at += len(batch)
            if not batch or start_at >= int(payload.get("total", start_at)):
                return issues

    async def get_comments(self, issue_key: str) -> list[JiraComment]:
        response = await self._request("GET", f"/rest/api/2/issue/{issue_key}/comment")
        return [
            JiraComment(
                body=item.get("body", ""),
                author=self._name(item.get("author")),
                created_at=item.get("created"),
            )
            for item in response.json().get("comments", [])
        ]

    async def get_attachments(self, issue_key: str) -> list[JiraAttachment]:
        issue = await self.get_issue(issue_key)
        return issue.attachments

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        async def operation() -> httpx.Response:
            started = time.perf_counter()
            try:
                response = await self._client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                raise ApiUnavailableError(str(exc)) from exc
            logger.info(
                "Jira API %s %s latency=%.3fs",
                method,
                path,
                time.perf_counter() - started,
            )
            if response.status_code in {401, 403}:
                raise AuthenticationError(
                    f"Jira API authentication failed ({response.status_code})"
                )
            if response.status_code == 404:
                raise ApiUnavailableError(f"Jira API endpoint unavailable: {path}")
            if response.status_code == 429:
                raise RateLimitError("Jira API rate limit exceeded")
            response.raise_for_status()
            return response

        return await retry_async(
            operation,
            attempts=self._config.retry_attempts,
            initial_delay=self._config.retry_initial_delay,
        )

    @staticmethod
    def _name(value: Any) -> str | None:
        return value.get("displayName") if isinstance(value, dict) else None

    @classmethod
    def _issue_from_json(cls, payload: dict[str, Any]) -> JiraIssue:
        fields = payload.get("fields", {})
        return JiraIssue(
            key=payload.get("key", ""),
            summary=fields.get("summary", ""),
            status=cls._name(fields.get("status")),
            priority=cls._name(fields.get("priority")),
            description=fields.get("description"),
            assignee=cls._name(fields.get("assignee")),
            reporter=cls._name(fields.get("reporter")),
            labels=fields.get("labels", []),
            components=[item.get("name", "") for item in fields.get("components", [])],
            fix_versions=[
                item.get("name", "") for item in fields.get("fixVersions", [])
            ],
            updated_at=fields.get("updated"),
            source_url=payload.get("self"),
        )
