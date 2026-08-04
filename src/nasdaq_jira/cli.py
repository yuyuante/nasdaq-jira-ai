"""Command-line entry point."""

import argparse
import asyncio
from pathlib import Path

from .config import load_config
from .crawler import JiraCrawler, SessionExpiredError
from .logging_config import configure_logging
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
    crawler = JiraCrawler(config.browser, config.crawler)
    if args.login:
        try:
            asyncio.run(crawler.login())
        except SessionExpiredError as exc:
            parser.exit(1, f"Login error: {exc}\n")
        return
    try:
        issues = asyncio.run(crawler.crawl())
    except SessionExpiredError as exc:
        parser.exit(1, f"Authentication error: {exc}\n")
    with SQLiteIssueRepository(config.database.path) as repository:
        saved = repository.upsert_many(issues)
        print(f"Saved {saved} issues; database contains {repository.count()} issues.")
