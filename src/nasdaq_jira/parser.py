"""Jira result page parser."""

from playwright.async_api import Locator, Page

from .models import JiraAttachment, JiraComment, JiraHistoryEntry, JiraIssue


class JiraIssueParser:
    """Convert configured Jira result rows into validated domain models."""

    def __init__(self, selectors: dict[str, str]) -> None:
        self._selectors = selectors

    async def parse_page(self, page: Page) -> list[JiraIssue]:
        """Parse all configured issue rows currently rendered on a page."""
        result: list[JiraIssue] = []
        for row in await page.locator(self._selectors["issue"]).all():
            key_locator = await self._self_or_child(row, "key")
            key_text = await key_locator.inner_text()
            issue_key = await key_locator.get_attribute("data-issue-key")
            key = issue_key or key_text.strip().split(maxsplit=1)[0]
            summary_text = await (
                await self._self_or_child(row, "summary")
            ).inner_text()
            href = await key_locator.get_attribute("href")
            result.append(
                JiraIssue(
                    key=key.strip(),
                    summary=summary_text.strip().removeprefix(key).strip(),
                    status=await self._optional_text(row, "status"),
                    priority=await self._optional_text(row, "priority"),
                    description=await self._optional_text(row, "description"),
                    assignee=await self._optional_text(row, "assignee"),
                    reporter=await self._optional_text(row, "reporter"),
                    labels=await self._list_text(row, "labels"),
                    components=await self._list_text(row, "components"),
                    fix_versions=await self._list_text(row, "fix_versions"),
                    comments=await self._comments(row),
                    attachments=await self._attachments(row),
                    history=await self._history(row),
                    updated_at=await self._optional_text(row, "updated_at"),
                    source_url=href,
                )
            )
        return result

    async def _self_or_child(self, row: Locator, field: str) -> Locator:
        locator = row.locator(self._selectors[field]).first
        if await locator.count() == 0 and await row.get_attribute("data-issue-key"):
            return row
        return locator

    async def _optional_text(self, row: Locator, field: str) -> str | None:
        selector = self._selectors.get(field, "")
        if not selector:
            return None
        locator = row.locator(selector).first
        if await locator.count() == 0:
            return None
        return (await locator.inner_text()).strip()

    async def _list_text(self, row: Locator, field: str) -> list[str]:
        selector = self._selectors.get(field, "")
        if not selector:
            return []
        return [
            value.strip() for value in await row.locator(selector).all_inner_texts()
        ]

    async def _comments(self, row: Locator) -> list[JiraComment]:
        selector = self._selectors.get("comment", "")
        if not selector:
            return []
        return [
            JiraComment(body=text.strip())
            for text in await row.locator(selector).all_inner_texts()
        ]

    async def _attachments(self, row: Locator) -> list[JiraAttachment]:
        selector = self._selectors.get("attachment", "")
        if not selector:
            return []
        locator = row.locator(selector)
        return [
            JiraAttachment(
                filename=(await item.inner_text()).strip(),
                url=await item.get_attribute("href"),
            )
            for item in await locator.all()
        ]

    async def _history(self, row: Locator) -> list[JiraHistoryEntry]:
        selector = self._selectors.get("history", "")
        if not selector:
            return []
        return [
            JiraHistoryEntry(details=text.strip())
            for text in await row.locator(selector).all_inner_texts()
        ]
