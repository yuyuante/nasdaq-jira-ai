"""Playwright-backed Jira data source."""

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
        for issue in await self._crawler.crawl():
            if issue.key == issue_key:
                return issue
        raise KeyError(issue_key)

    async def search_issues(self, jql: str) -> list[JiraIssue]:
        return await self._crawler.crawl()

    async def get_comments(self, issue_key: str) -> list[JiraComment]:
        return (await self.get_issue(issue_key)).comments

    async def get_attachments(self, issue_key: str) -> list[JiraAttachment]:
        return (await self.get_issue(issue_key)).attachments