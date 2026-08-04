"""Jira result page parser."""

from playwright.async_api import Locator, Page

from .models import JiraIssue


class JiraIssueParser:
    """Convert configured Jira result rows into domain models."""

    def __init__(self, selectors: dict[str, str]) -> None:
        self._selectors = selectors

    async def parse_page(self, page: Page) -> list[JiraIssue]:
        """Parse all issue rows currently rendered on a page."""
        result: list[JiraIssue] = []
        for row in await page.locator(self._selectors["issue"]).all():
            key_locator = row.locator(self._selectors["key"]).first
            key = await key_locator.inner_text()
            summary = await row.locator(self._selectors["summary"]).first.inner_text()
            status = await self._optional_text(row, self._selectors.get("status"))
            updated_at = await self._optional_text(
                row, self._selectors.get("updated_at")
            )
            href = await key_locator.get_attribute("href")
            result.append(
                JiraIssue(key.strip(), summary.strip(), status, updated_at, href)
            )
        return result

    @staticmethod
    async def _optional_text(row: Locator, selector: str | None) -> str | None:
        if not selector:
            return None
        locator = row.locator(selector).first
        if await locator.count() == 0:
            return None
        return (await locator.inner_text()).strip()
