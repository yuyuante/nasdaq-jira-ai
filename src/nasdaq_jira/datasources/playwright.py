"""Playwright-backed Jira data source."""

import re

from ..config import BrowserConfig, CrawlerConfig
from ..crawler import JiraCrawler
from ..models import JiraAttachment, JiraComment, JiraIssue
from .base import JiraDataSource


class JiraPlaywrightDataSource(JiraDataSource):
    """Adapt the existing authenticated Playwright crawler to the contract."""

    def __init__(self, browser: BrowserConfig, crawler: CrawlerConfig) -> None:
        self._crawler = JiraCrawler(browser, crawler)

    async def login(self) -> None:
        await self._crawler.login()

    async def get_issue(self, issue_key: str) -> JiraIssue:
        for issue in await self._crawler.crawl(issue_key=issue_key):
            if issue.key == issue_key:
                return issue
        raise KeyError(issue_key)

    async def search_issues(self, jql: str) -> list[JiraIssue]:
        match = re.search(
            r"\bkey\s*=\s*[\"']?([A-Z][A-Z0-9_]*-\d+)",
            jql,
            re.IGNORECASE,
        )
        issue_key = match.group(1).upper() if match else None
        return await self._crawler.crawl(issue_key=issue_key)

    async def get_comments(self, issue_key: str) -> list[JiraComment]:
        return (await self.get_issue(issue_key)).comments

    async def get_attachments(self, issue_key: str) -> list[JiraAttachment]:
        return (await self.get_issue(issue_key)).attachments
