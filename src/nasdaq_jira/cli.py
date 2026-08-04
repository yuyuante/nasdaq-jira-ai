"""Command-line entry point."""

import argparse
import asyncio
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import AppConfig, load_config
from .datasources import create_data_source
from .datasources.exceptions import AuthenticationError, PlaywrightError
from .datasources.playwright import JiraPlaywrightDataSource
from .logging_config import configure_logging
from .models import JiraIssue
from .storage import SQLiteIssueRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl Nasdaq Jira issues")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--login", action="store_true", help="save Playwright login state"
    )
    args = parser.parse_args()
    config = load_config(args.config)
    configure_logging(
        config.logging.level, config.logging.file, config.logging.backup_count
    )
    if args.login:
        source = JiraPlaywrightDataSource(config.browser, config.crawler)
        try:
            asyncio.run(source.login())
        except Exception as exc:
            parser.exit(1, f"Login error: {exc}\n")
        return
    try:
        issues = asyncio.run(_crawl(config))
    except (AuthenticationError, PlaywrightError, RuntimeError) as exc:
        parser.exit(1, f"Crawl error: {exc}\n")
    with SQLiteIssueRepository(config.database.path) as repository:
        saved = repository.upsert_many(issues)
        print(f"Saved {saved} issues; database contains {repository.count()} issues.")


async def _crawl(config: AppConfig) -> list[JiraIssue]:
    source = await create_data_source(config)
    jql = parse_qs(urlparse(config.crawler.search_url).query).get("jql", [""])[0]
    try:
        return await source.search_issues(jql)
    finally:
        close = getattr(source, "close", None)
        if close is not None:
            await close()
