"""Playwright-based Jira search crawler with session management."""

import asyncio
import logging
from functools import partial
from pathlib import Path

from playwright.async_api import (
    Browser,
    BrowserContext,
    Locator,
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


async def _click_next_page(link: Locator) -> None:
    await link.click()


class JiraCrawler:
    """Coordinate browser navigation and delegate result parsing."""

    def __init__(self, browser: BrowserConfig, crawler: CrawlerConfig) -> None:
        self._browser_config = browser
        self._crawler_config = crawler
        self._parser = JiraIssueParser(crawler.selectors)

    async def login(self) -> None:
        """Run interactive login, including MFA, and save the browser state."""
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=False)
            context = await browser.new_context()
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

    async def crawl(self) -> list[JiraIssue]:
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
                issues = await self._crawl_pages(page)
                logger.info("Crawled %d Jira issues", len(issues))
                return issues
            finally:
                await context.close()
                await browser.close()

    async def _new_context(self, browser: Browser, state_path: Path) -> BrowserContext:
        """Create a browser context and turn invalid state into a clear error."""
        try:
            return await browser.new_context(storage_state=str(state_path))
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

    async def _crawl_pages(self, page: Page) -> list[JiraIssue]:
        issues: list[JiraIssue] = []
        await retry_async(
            lambda: page.goto(
                self._crawler_config.search_url, wait_until="domcontentloaded"
            )
        )
        for _ in range(self._crawler_config.max_pages):
            await self._assert_authenticated(page)
            await page.wait_for_selector(self._crawler_config.selectors["issue"])
            issues.extend(await self._parser.parse_page(page))
            next_link = page.locator(self._crawler_config.selectors["next_page"]).first
            if not await next_link.is_visible():
                break
            await retry_async(partial(_click_next_page, next_link))
        return issues
