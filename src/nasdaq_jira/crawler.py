"""Playwright-based Jira search crawler."""

import asyncio
import logging
from functools import partial

from playwright.async_api import Locator, Page, async_playwright

from .config import BrowserConfig, CrawlerConfig
from .models import JiraIssue
from .retry import retry_async

logger = logging.getLogger(__name__)


async def _click_next_page(link: Locator) -> None:
    await link.click()


class JiraCrawler:
    def __init__(self, browser: BrowserConfig, crawler: CrawlerConfig) -> None:
        self._browser_config = browser
        self._crawler_config = crawler

    async def login(self) -> None:
        """Open a headed browser and save the authenticated session."""
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(
                self._crawler_config.search_url, wait_until="domcontentloaded"
            )
            print("Complete Jira login in the browser, then press Enter here.")
            await asyncio.to_thread(input)
            state_path = self._browser_config.storage_state_path
            state_path.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(state_path))
            await browser.close()

    async def crawl(self) -> list[JiraIssue]:
        """Crawl configured search result pages."""
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=self._browser_config.headless
            )
            state = self._browser_config.storage_state_path
            if state.exists():
                context = await browser.new_context(storage_state=str(state))
            else:
                context = await browser.new_context()
            page = await context.new_page()
            page.set_default_timeout(self._browser_config.timeout_ms)
            try:
                issues = await self._crawl_pages(page)
                logger.info("Crawled %d Jira issues", len(issues))
                return issues
            finally:
                await context.close()
                await browser.close()

    async def _crawl_pages(self, page: Page) -> list[JiraIssue]:
        issues: list[JiraIssue] = []
        await retry_async(
            lambda: page.goto(
                self._crawler_config.search_url, wait_until="domcontentloaded"
            )
        )
        for _ in range(self._crawler_config.max_pages):
            await page.wait_for_selector(self._crawler_config.selectors["issue"])
            issues.extend(await self._parse_page(page))
            next_link = page.locator(self._crawler_config.selectors["next_page"]).first
            if not await next_link.is_visible():
                break
            await retry_async(partial(_click_next_page, next_link))
        return issues

    async def _parse_page(self, page: Page) -> list[JiraIssue]:
        selectors = self._crawler_config.selectors
        result: list[JiraIssue] = []
        for row in await page.locator(selectors["issue"]).all():
            key = await row.locator(selectors["key"]).first.inner_text()
            summary = await row.locator(selectors["summary"]).first.inner_text()
            status = await self._optional_text(row, selectors.get("status"))
            updated_at = await self._optional_text(row, selectors.get("updated_at"))
            href = await row.locator(selectors["key"]).first.get_attribute("href")
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
