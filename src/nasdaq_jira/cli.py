"""Command-line entry point."""

import argparse
import asyncio
from pathlib import Path

from .config import load_config
from .crawler import JiraCrawler
from .logging_config import configure_logging
from .repository import SQLiteIssueRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl Nasdaq Jira issues")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--login", action="store_true", help="save Playwright login state"
    )
    args = parser.parse_args()
    config = load_config(args.config)
    configure_logging(config.logging.level, config.logging.file)
    crawler = JiraCrawler(config.browser, config.crawler)
    if args.login:
        asyncio.run(crawler.login())
        return
    issues = asyncio.run(crawler.crawl())
    with SQLiteIssueRepository(config.database.path) as repository:
        saved = repository.upsert_many(issues)
        print(f"Saved {saved} issues; database contains {repository.count()} issues.")
