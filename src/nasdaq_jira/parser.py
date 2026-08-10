"""Jira result and detail page parser."""

import re

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .models import (
    JiraAttachment,
    JiraComment,
    JiraHistoryChange,
    JiraHistoryEntry,
    JiraIssue,
    JiraIssueDetails,
)

_ISSUE_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*-\d+$")


def is_valid_jira_issue_key(value: str) -> bool:
    """Return whether a value matches Jira's PROJECT-123 issue key format."""
    return _ISSUE_KEY_PATTERN.fullmatch(value.strip()) is not None


def summarize_text(value: str, max_chars: int = 280) -> str:
    """Create a deterministic, short extractive summary without external calls."""
    clean = " ".join(value.split())
    if len(clean) <= max_chars:
        return clean
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    summary = " ".join(sentences[:2]).strip()
    if len(summary) <= max_chars:
        return summary
    return summary[: max_chars - 1].rstrip() + "…"


def summarize_comments(comments: list[JiraComment]) -> str:
    """Summarize every comment independently and preserve their order."""
    summaries = [
        f"{index}. {summarize_text(comment.body)}"
        for index, comment in enumerate(comments, start=1)
        if comment.body.strip()
    ]
    return "\n".join(summaries)


class JiraIssueParser:
    """Convert configured Jira result and detail pages into domain models."""

    def __init__(
        self, selectors: dict[str, str], activity_timeout_ms: int = 2000
    ) -> None:
        self._selectors = selectors
        self._activity_timeout_ms = activity_timeout_ms

    async def parse_page(self, page: Page) -> list[JiraIssue]:
        """Parse all configured issue links currently rendered on a page."""
        result: list[JiraIssue] = []
        for row in await page.locator(self._selectors["issue"]).all():
            key_locator = await self._self_or_child(row, "key")
            key_text = await key_locator.inner_text()
            issue_key = await key_locator.get_attribute("data-issue-key")
            key = (issue_key or key_text.strip().split(maxsplit=1)[0]).strip()
            if not is_valid_jira_issue_key(key):
                continue
            summary_text = await (
                await self._self_or_child(row, "summary")
            ).inner_text()
            href = await key_locator.get_attribute("href")
            result.append(
                JiraIssue(
                    key=key,
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

    async def parse_detail_page(self, page: Page, issue: JiraIssue) -> JiraIssue:
        """Enrich a search result with all available detail-page fields."""
        details = JiraIssueDetails(
            issue_type=await self._page_optional_text(page, "detail_issue_type"),
            resolution=await self._page_optional_text(page, "detail_resolution"),
            affects_versions=await self._page_list_text(
                page, "detail_affects_versions"
            ),
            service_product=await self._page_optional_text(
                page, "detail_service_product"
            ),
            created_at=await self._page_optional_text(
                page, "detail_created_at", wait_for_attached=True
            ),
        )
        comments = await self._page_comments(page)
        try:
            history = await self._page_history(page)
        except RuntimeError as exc:
            raise RuntimeError(
                f"Failed to load Jira history for {issue.key}: {exc}"
            ) from exc
        resolution_summary = summarize_comments(comments) or None
        updates: dict[str, object] = {
            "details": details,
            "comments": comments,
            "history": history,
            "resolution_summary": resolution_summary,
            "updated_at": await self._page_optional_text(
                page, "detail_updated_at", wait_for_attached=True
            ),
        }
        for field, selector_key in (
            ("summary", "detail_summary"),
            ("status", "detail_status"),
            ("priority", "detail_priority"),
            ("description", "detail_description"),
            ("assignee", "detail_assignee"),
            ("reporter", "detail_reporter"),
        ):
            value = await self._page_optional_text(page, selector_key)
            if value is not None:
                updates[field] = value
        for field, selector_key in (
            ("labels", "detail_labels"),
            ("components", "detail_components"),
            ("fix_versions", "detail_fix_versions"),
        ):
            updates[field] = await self._page_list_text(page, selector_key)
        updates["attachments"] = await self._page_attachments(page)
        return issue.model_copy(update=updates)

    async def _page_comments(self, page: Page) -> list[JiraComment]:
        tab_selector = self._selectors.get("detail_comments_tab", "")
        if tab_selector:
            tab = page.locator(tab_selector).first
            try:
                await tab.wait_for(state="attached", timeout=self._activity_timeout_ms)
            except PlaywrightTimeoutError as exc:
                raise RuntimeError("Jira Comments tab was not found") from exc
            try:
                await tab.click(timeout=self._activity_timeout_ms)
            except (PlaywrightError, PlaywrightTimeoutError) as exc:
                raise RuntimeError("Jira Comments tab could not be loaded") from exc
        selector = self._selectors.get("detail_comments", "")
        if not selector:
            return []
        locator = page.locator(selector)
        try:
            await locator.first.wait_for(
                state="attached", timeout=self._activity_timeout_ms
            )
        except PlaywrightTimeoutError:
            return []
        comments: list[JiraComment] = []
        for index, item in enumerate(await locator.all()):
            body = re.sub(
                r"^\\s*commented by .*?(?:\\r?\\n)+",
                "",
                (await item.inner_text()).strip(),
                flags=re.IGNORECASE,
            )
            if not body:
                continue
            container = item.locator(
                "xpath=ancestor::div[contains(@class, 'activity-comment')][1]"
            )
            if not await container.count():
                continue
            comment_id = await container.get_attribute(
                "id"
            ) or await item.get_attribute("data-comment-id")
            author_locator = container.locator("a.user-hover").first
            author = (
                (await author_locator.inner_text()).strip()
                if await author_locator.count()
                else None
            )
            time_locator = container.locator("time[datetime]").first
            created_at = (
                await time_locator.get_attribute("datetime")
                if await time_locator.count()
                else None
            )
            comments.append(
                JiraComment(
                    comment_id=comment_id or f"comment-{index}",
                    body=body,
                    summary=summarize_text(body),
                    author=author or None,
                    created_at=created_at,
                )
            )
        return comments

    async def _page_history(self, page: Page) -> list[JiraHistoryEntry]:
        tab_selector = self._selectors.get("detail_history_tab", "")
        if tab_selector:
            tab = page.locator(tab_selector).first
            try:
                await tab.wait_for(state="attached", timeout=self._activity_timeout_ms)
            except PlaywrightTimeoutError as exc:
                raise RuntimeError("Jira History tab was not found") from exc
            try:
                await tab.click(timeout=self._activity_timeout_ms)
            except (PlaywrightError, PlaywrightTimeoutError) as exc:
                raise RuntimeError("Jira History tab could not be loaded") from exc

        selector = self._selectors.get("detail_history", "")
        if not selector:
            return []
        locator = page.locator(selector)
        try:
            await locator.first.wait_for(
                state="attached", timeout=self._activity_timeout_ms
            )
        except PlaywrightTimeoutError as exc:
            raise RuntimeError("Jira History entries did not load") from exc
        history: list[JiraHistoryEntry] = []
        for index, item in enumerate(await locator.all()):
            details = (await item.inner_text()).strip()
            if not details:
                continue
            container = item.locator("xpath=..").first
            author_locator = container.locator("a.user-hover").first
            author = (
                (await author_locator.inner_text()).strip()
                if await author_locator.count()
                else None
            )
            time_locator = container.locator("time[datetime]").first
            created_at = (
                await time_locator.get_attribute("datetime")
                if await time_locator.count()
                else None
            )
            changes: list[JiraHistoryChange] = []
            for row in await item.locator("tr").all():
                field_locator = row.locator(".activity-name").first
                if not await field_locator.count():
                    continue
                field = " ".join((await field_locator.inner_text()).split())
                old_value = await self._history_value(row, ".activity-old-val")
                new_value = await self._history_value(row, ".activity-new-val")
                changes.append(
                    JiraHistoryChange(
                        field=field,
                        old_value=old_value,
                        new_value=new_value,
                    )
                )
            if changes:
                details = "; ".join(
                    f"{change.field}: {change.old_value or '(none)'} -> "
                    f"{change.new_value or '(none)'}"
                    for change in changes
                )
            history_id = await item.locator("table").first.get_attribute("id")
            history.append(
                JiraHistoryEntry(
                    history_id=history_id or f"history-{index}",
                    details=details,
                    author=author or None,
                    created_at=created_at,
                    changes=changes,
                )
            )
        return history

    @staticmethod
    async def _history_value(row: Locator, selector: str) -> str | None:
        locator = row.locator(selector).first
        if not await locator.count():
            return None
        value = " ".join((await locator.inner_text()).split())
        return re.sub(r"^(?:Original|New):\s*", "", value, flags=re.IGNORECASE) or None

    async def _page_attachments(self, page: Page) -> list[JiraAttachment]:
        selector = self._selectors.get("detail_attachments", "")
        if not selector:
            return []
        return [
            JiraAttachment(
                filename=(await item.inner_text()).strip(),
                url=await item.get_attribute("href"),
            )
            for item in await page.locator(selector).all()
        ]

    async def _self_or_child(self, row: Locator, field: str) -> Locator:
        row_href = await row.get_attribute("href")
        is_issue_link = await row.get_attribute("data-issue-key") or (
            row_href is not None and "/jira/browse/" in row_href
        )
        if field in {"key", "summary"} and is_issue_link:
            return row
        locator = row.locator(self._selectors[field]).first
        if await locator.count() == 0 and is_issue_link:
            return row
        return locator

    async def _page_optional_text(
        self,
        page: Page,
        field: str,
        *,
        wait_for_attached: bool = False,
    ) -> str | None:
        selector = self._selectors.get(field, "")
        if not selector:
            return None
        locator = page.locator(selector).first
        try:
            if wait_for_attached:
                await locator.wait_for(
                    state="attached", timeout=self._activity_timeout_ms
                )
            elif await locator.count() == 0:
                return None
            value = await locator.inner_text(timeout=self._activity_timeout_ms)
            return value.strip() or None
        except PlaywrightTimeoutError:
            return None

    async def _page_list_text(self, page: Page, field: str) -> list[str]:
        selector = self._selectors.get(field, "")
        if not selector:
            return []
        return [
            value.strip() for value in await page.locator(selector).all_inner_texts()
        ]

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
            JiraComment(body=text.strip(), summary=summarize_text(text))
            for text in await row.locator(selector).all_inner_texts()
        ]

    async def _attachments(self, row: Locator) -> list[JiraAttachment]:
        selector = self._selectors.get("attachment", "")
        if not selector:
            return []
        return [
            JiraAttachment(
                filename=(await item.inner_text()).strip(),
                url=await item.get_attribute("href"),
            )
            for item in await row.locator(selector).all()
        ]

    async def _history(self, row: Locator) -> list[JiraHistoryEntry]:
        selector = self._selectors.get("history", "")
        if not selector:
            return []
        return [
            JiraHistoryEntry(details=text.strip())
            for text in await row.locator(selector).all_inner_texts()
        ]
