"""Playwright-based Jira search crawler with session management."""

import asyncio
import logging
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
)
from playwright.async_api import (
    Error as PlaywrightError,
)

from .config import BrowserConfig, CrawlerConfig
from .models import JiraIssue
from .parser import JiraIssueParser
from .retry import retry_async

logger = logging.getLogger(__name__)


class SessionExpiredError(RuntimeError):
    """Raised when the saved Jira browser session is missing or expired."""


async def _goto_page(page: Page, url: str) -> None:

    await page.goto(url, wait_until="domcontentloaded")


async def _goto_page_with_retry(page: Page, url: str) -> None:

    await retry_async(lambda: _goto_page(page, url))


async def _goto_detail_page(page: Page, url: str, selector: str) -> None:
    await page.goto(url, wait_until="commit")
    await page.locator(selector).first.wait_for(state="attached")


async def _goto_detail_page_with_retry(page: Page, url: str, selector: str) -> None:
    await retry_async(lambda: _goto_detail_page(page, url, selector))


class JiraCrawler:
    """Coordinate browser navigation and delegate result parsing."""

    def __init__(self, browser: BrowserConfig, crawler: CrawlerConfig) -> None:

        self._browser_config = browser

        self._crawler_config = crawler

        self._parser = JiraIssueParser(
            crawler.selectors, crawler.detail_activity_timeout_ms
        )

    async def login(self) -> None:
        """Run interactive login, including MFA, and save the browser state."""

        async with async_playwright() as playwright:

            browser = await playwright.chromium.launch(headless=False)

            context = await browser.new_context(viewport=None)

            try:

                page = await context.new_page()

                page.set_default_timeout(self._browser_config.timeout_ms)

                await page.goto(
                    self._crawler_config.search_url, wait_until="domcontentloaded"
                )

                print(
                    "Complete Jira login and any MFA challenge in the browser, "
                    "then press Enter here."
                )

                await asyncio.to_thread(input)

                await self._assert_authenticated(page, login_flow=True)

                state_path = self._browser_config.storage_state_path

                state_path.parent.mkdir(parents=True, exist_ok=True)

                await context.storage_state(path=str(state_path))

                logger.info("Saved authenticated Playwright state to %s", state_path)

            finally:

                await context.close()

                await browser.close()

    async def crawl(self, issue_key: str | None = None) -> list[JiraIssue]:
        """Crawl configured search result pages using the saved session."""

        state_path = self._browser_config.storage_state_path

        if not state_path.exists():

            raise SessionExpiredError(
                f"No Playwright session state found at {state_path}. "
                "Run the CLI with --login to complete interactive login and MFA."
            )

        async with async_playwright() as playwright:

            browser = await playwright.chromium.launch(
                headless=self._browser_config.headless
            )

            context = await self._new_context(browser, state_path)

            page = await context.new_page()

            page.set_default_timeout(self._browser_config.timeout_ms)

            try:

                issues = await self._crawl_pages(page, issue_key)

                logger.info("Crawled %d Jira issues", len(issues))

                return issues

            finally:

                await context.close()

                await browser.close()

    async def _new_context(self, browser: Browser, state_path: Path) -> BrowserContext:
        """Create a browser context and turn invalid state into a clear error."""

        try:

            return await browser.new_context(
                storage_state=str(state_path), viewport=None
            )

        except PlaywrightError as exc:

            raise SessionExpiredError(
                f"Unable to load Playwright session state at {state_path}. "
                "The state may be invalid or expired; run the CLI with --login."
            ) from exc

    async def _assert_authenticated(
        self, page: Page, *, login_flow: bool = False
    ) -> None:
        """Verify the configured authenticated marker is visible."""

        try:

            authenticated = page.locator(
                self._browser_config.authenticated_selector
            ).first

            if await authenticated.count() > 0 and await authenticated.is_visible():

                return

            login_form = page.locator(self._browser_config.login_selector).first

            if await login_form.count() > 0 and await login_form.is_visible():

                if login_flow:

                    raise SessionExpiredError(
                        "Login was not completed. The configured login selector is "
                        "still visible after the MFA step."
                    )

                raise SessionExpiredError(
                    "The Jira session is missing or expired. Run the CLI with "
                    "--login to authenticate again."
                )

        except PlaywrightError as exc:

            raise SessionExpiredError(
                "Could not inspect the Jira authentication selectors. "
                "Check browser.authenticated_selector and browser.login_selector."
            ) from exc

        raise SessionExpiredError(
            "Could not verify Jira authentication. Configure a visible "
            "browser.authenticated_selector for the logged-in page, then run "
            "the CLI with --login."
        )

    async def _crawl_pages(
        self, page: Page, issue_key: str | None = None
    ) -> list[JiraIssue]:
        issues_by_key: dict[str, JiraIssue] = {}
        current_start_index = 0
        await _goto_page_with_retry(page, self._crawler_config.search_url)
        for _ in range(self._crawler_config.max_pages):
            await self._assert_authenticated(page)
            await self._wait_for_issue_list(page)
            page_issues = await self._parser.parse_page(page)
            pending = [
                issue
                for issue in page_issues
                if issue.key not in issues_by_key
                and (issue_key is None or issue.key == issue_key)
            ]
            concurrency = self._crawler_config.detail_concurrency
            batches = [
                pending[index::concurrency]
                for index in range(concurrency)
                if pending[index::concurrency]
            ]
            enriched_batches = await asyncio.gather(
                *(
                    self._enrich_issue_batch(
                        page.context,
                        batch,
                        continue_on_error=issue_key is None,
                    )
                    for batch in batches
                )
            )
            for batch in enriched_batches:
                for issue in batch:
                    issues_by_key[issue.key] = issue
            if issue_key and issue_key in issues_by_key:
                return [issues_by_key[issue_key]]
            next_page = await self._next_page_url(page, current_start_index)
            if next_page is None:
                break
            current_start_index = self._start_index(next_page)
            await _goto_page_with_retry(page, next_page)
        if issue_key and issue_key not in issues_by_key:
            raise RuntimeError(f"Issue {issue_key} was not found in Jira search results")
        return list(issues_by_key.values())
    async def _enrich_issue_batch(
        self,
        context: BrowserContext,
        issues: list[JiraIssue],
        *,
        continue_on_error: bool = True,
    ) -> list[JiraIssue]:
        detail_page = await context.new_page()
        detail_page.set_default_timeout(self._browser_config.timeout_ms)
        try:
            enriched: list[JiraIssue] = []
            for issue in issues:
                try:
                    if issue.source_url:
                        detail_url = urljoin(
                            self._crawler_config.search_url, issue.source_url
                        )
                        await _goto_detail_page_with_retry(
                            detail_page,
                            detail_url,
                            self._crawler_config.selectors["detail_summary"],
                        )
                        await self._assert_authenticated(detail_page)
                        issue = await self._parser.parse_detail_page(detail_page, issue)
                    enriched.append(issue)
                except SessionExpiredError as exc:
                    message = (
                        f"Failed to enrich issue={issue.key}: "
                        f"authentication/session error: {exc}"
                    )
                    logger.error(message)
                    raise RuntimeError(message) from exc
                except Exception as exc:
                    message = (
                        f"Failed to enrich issue={issue.key}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    logger.exception("%s%s", message, "; continuing with next issue" if continue_on_error else "")
                    if not continue_on_error:
                        raise RuntimeError(message) from exc
            return enriched
        finally:
            await detail_page.close()

    async def _next_page_url(self, page: Page, current_start_index: int) -> str | None:
        """Return the next Jira numeric pagination URL."""

        candidates: list[tuple[int, str]] = []

        locator = page.locator(self._crawler_config.selectors["next_page"])

        for link in await locator.all():

            href = await link.get_attribute("href")

            if not href:

                continue

            start_index = self._start_index(href)

            if start_index > current_start_index:

                candidates.append((start_index, urljoin(page.url, href)))

        if not candidates:

            return None

        return min(candidates, key=lambda item: item[0])[1]

    @staticmethod
    def _start_index(url: str) -> int:
        """Extract a Jira startIndex parameter, defaulting to the first page."""

        value = parse_qs(urlparse(url).query).get("startIndex", ["0"])[0]

        try:

            return int(value)

        except ValueError:

            return 0

    async def _wait_for_issue_list(self, page: Page) -> None:
        """Wait until Jira's dynamically rendered issue list stabilizes."""

        locator = page.locator(self._crawler_config.selectors["issue"])

        await locator.first.wait_for(state="attached")

        previous_count = -1

        stable_polls = 0

        poll_interval_ms = 250

        required_stable_polls = 8

        deadline = asyncio.get_running_loop().time() + (
            self._browser_config.timeout_ms / 1000
        )

        while asyncio.get_running_loop().time() < deadline:

            current_count = await locator.count()

            if current_count == previous_count:

                stable_polls += 1

            else:

                stable_polls = 0

                previous_count = current_count

            if stable_polls >= required_stable_polls:

                return

            await page.wait_for_timeout(poll_interval_ms)
