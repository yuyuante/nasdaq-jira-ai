"""YAML configuration loading and validation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class BrowserConfig:
    headless: bool
    timeout_ms: int
    storage_state_path: Path


@dataclass(frozen=True, slots=True)
class CrawlerConfig:
    search_url: str
    max_pages: int
    page_size: int
    selectors: dict[str, str]


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    path: Path


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    level: str
    file: Path
    backup_count: int


@dataclass(frozen=True, slots=True)
class AppConfig:
    browser: BrowserConfig
    crawler: CrawlerConfig
    database: DatabaseConfig
    logging: LoggingConfig


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"Missing or invalid configuration section: {name}")
    return value


def load_config(path: Path) -> AppConfig:
    """Load and validate an application YAML configuration."""
    with path.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream) or {}
    if not isinstance(raw, dict):
        raise ValueError("Configuration root must be a YAML mapping")

    browser = _section(raw, "browser")
    crawler = _section(raw, "crawler")
    database = _section(raw, "database")
    logging = _section(raw, "logging")
    selectors = crawler.get("selectors")
    if not isinstance(selectors, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in selectors.items()
    ):
        raise ValueError("crawler.selectors must be a mapping of strings")
    required = {"issue", "key", "summary", "next_page"}
    missing = required - selectors.keys()
    if missing:
        raise ValueError(f"Missing selectors: {', '.join(sorted(missing))}")

    return AppConfig(
        browser=BrowserConfig(
            headless=bool(browser.get("headless", True)),
            timeout_ms=int(browser.get("timeout_ms", 30000)),
            storage_state_path=Path(
                browser.get("storage_state_path", "storage_state.json")
            ),
        ),
        crawler=CrawlerConfig(
            search_url=str(crawler["search_url"]),
            max_pages=int(crawler.get("max_pages", 10)),
            page_size=int(crawler.get("page_size", 50)),
            selectors=selectors,
        ),
        database=DatabaseConfig(
            path=Path(database.get("path", "data/nasdaq_jira.sqlite3"))
        ),
        logging=LoggingConfig(
            level=str(logging.get("level", "INFO")),
            file=Path(logging.get("file", "logs/nasdaq-jira.log")),
            backup_count=int(logging.get("backup_count", 14)),
        ),
    )
