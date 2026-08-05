"""Command-line entry point."""

import argparse
import asyncio
from pathlib import Path

from .config import AppConfig, load_config
from .datasources import create_data_source
from .datasources.exceptions import AuthenticationError, PlaywrightError
from .datasources.playwright import JiraPlaywrightDataSource
from .logging_config import configure_logging
from .models import JiraIssue
from .rag.engine import RagEngine
from .rag.providers import OpenAIProvider
from .rag.vector_store import SQLiteFts5VectorStore
from .storage import SQLiteIssueRepository
from .sync.engine import SyncEngine, jql_from_search_url


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl Nasdaq Jira issues")
    parser.add_argument("command", nargs="?", choices=("sync", "ask"), default=None)
    parser.add_argument("query", nargs="?")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--login", action="store_true", help="save Playwright login state"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--full", action="store_true", help="run a full synchronization")
    mode.add_argument(
        "--incremental", action="store_true", help="run incremental synchronization"
    )
    mode.add_argument(
        "--resume", action="store_true", help="resume an interrupted synchronization"
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
        if args.command == "ask":
            if not args.query:
                parser.error("ask requires a question")
            asyncio.run(_ask(config, args.query))
        elif args.command == "sync":
            asyncio.run(_sync(config, args))
        else:
            issues = asyncio.run(_crawl(config))
            with SQLiteIssueRepository(config.database.path) as repository:
                saved = repository.upsert_many(issues)
                print(
                    f"Saved {saved} issues; "
                    f"database contains {repository.count()} issues."
                )
    except (AuthenticationError, PlaywrightError, RuntimeError) as exc:
        parser.exit(1, f"Crawl error: {exc}\n")


async def _crawl(config: AppConfig) -> list[JiraIssue]:
    source = await create_data_source(config)
    try:
        return await source.search_issues(
            jql_from_search_url(config.crawler.search_url)
        )
    finally:
        close = getattr(source, "close", None)
        if close is not None:
            await close()


async def _sync(config: AppConfig, args: argparse.Namespace) -> None:
    source = await create_data_source(config)
    try:
        with SQLiteIssueRepository(config.database.path) as repository:
            engine = SyncEngine(
                source,
                repository,
                config.sync,
                jql_from_search_url(config.crawler.search_url),
            )
            if args.full:
                metrics = await engine.full_sync()
            elif args.resume:
                metrics = await engine.resume_sync()
            else:
                metrics = await engine.incremental_sync()
            print(metrics)
    finally:
        close = getattr(source, "close", None)
        if close is not None:
            await close()


async def _ask(config: AppConfig, query: str) -> None:
    if not config.rag.enabled or not config.rag.api_key:
        raise RuntimeError("RAG is disabled or rag.api_key is not configured")
    provider = OpenAIProvider(
        config.rag.api_key,
        config.rag.base_url,
        config.rag.embedding_model,
        config.rag.answer_model,
    )
    store = SQLiteFts5VectorStore(config.database.path)
    try:
        with SQLiteIssueRepository(config.database.path) as repository:
            engine = RagEngine(config.rag, provider, store, provider)
            await engine.index(repository.all_issues())
            answer = await engine.ask(query)
            print(answer.model_dump_json(indent=2))
    finally:
        store.close()
        await provider.close()
