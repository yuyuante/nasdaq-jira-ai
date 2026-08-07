"""Command-line entry point."""

import argparse
import asyncio
import sys
from pathlib import Path

from .changes import ChangeReport
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
    parser.add_argument(
        "command", nargs="?", choices=("sync", "ask", "show"), default=None
    )
    parser.add_argument("query", nargs="?")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--all-comments",
        action="store_true",
        help="include all stored comments in show output",
    )
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
        elif args.command == "show":
            if not args.query:
                parser.error("show requires an issue key")
            _show(config, args.query, args.all_comments)
        elif args.command == "sync":
            asyncio.run(_sync(config, args))
        else:
            issues = asyncio.run(_crawl(config))
            with SQLiteIssueRepository(config.database.path) as repository:
                report = ChangeReport.from_repository(repository, issues)
                saved = repository.upsert_many(issues)
                print(format_change_report(report))
                print(
                    f"Saved {saved} issues; "
                    f"database contains {repository.count()} issues."
                )
    except (AuthenticationError, PlaywrightError, RuntimeError) as exc:
        parser.exit(1, f"Crawl error: {exc}\n")


def _show(config: AppConfig, issue_key: str, all_comments: bool = False) -> None:
    """Print one locally stored Jira issue and its activity summaries."""
    with SQLiteIssueRepository(config.database.path) as repository:
        issue = repository.get_issue(issue_key)
    if issue is None:
        raise RuntimeError(
            f"Issue {issue_key} was not found in the local database. "
            "Run crawl or sync first."
        )
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(errors="replace")
    print(_format_issue(issue, all_comments=all_comments))


def _format_issue(issue: JiraIssue, *, all_comments: bool = False) -> str:
    """Render an issue for terminal users without requiring an AI provider."""
    lines = [
        f"Key: {issue.key}",
        f"Summary: {issue.summary or '(none)'}",
        f"Status: {issue.status or '(none)'}",
        f"Priority: {issue.priority or '(none)'}",
        f"Assignee: {issue.assignee or '(none)'}",
        f"Reporter: {issue.reporter or '(none)'}",
        f"Resolution: {issue.details.resolution or '(none)'}",
        f"Resolution summary: {issue.resolution_summary or '(none)'}",
        f"Labels: {', '.join(issue.labels) or '(none)'}",
        f"Components: {', '.join(issue.components) or '(none)'}",
        f"Fix versions: {', '.join(issue.fix_versions) or '(none)'}",
        f"Affects versions: {', '.join(issue.details.affects_versions) or '(none)'}",
        f"Service product: {issue.details.service_product or '(none)'}",
        f"Created: {issue.details.created_at or '(none)'}",
        f"Updated: {issue.updated_at or '(none)'}",
        "",
        "Description:",
        issue.description or "(none)",
        "",
        f"Comments count: {len(issue.comments)}",
        "Comments summary:",
        issue.resolution_summary or "(none)",
    ]
    if all_comments:
        lines.append("")
        lines.append("All comments:")
        for index, comment in enumerate(issue.comments, start=1):
            author = comment.author or "unknown author"
            created_at = comment.created_at or "unknown time"
            lines.append(f"{index}. [{created_at}] {author}: {comment.body}")
    lines.extend(["", f"Attachments ({len(issue.attachments)}):"])
    for attachment in issue.attachments:
        lines.append(f"- {attachment.filename}: {attachment.url or '(no URL)'}")
    lines.extend(["", f"History ({len(issue.history)}):"])
    for entry in issue.history:
        author = entry.author or "unknown author"
        created_at = entry.created_at or "unknown time"
        lines.append(f"- [{created_at}] {author}: {entry.details}")
    return "\n".join(lines)


def format_change_report(report: ChangeReport) -> str:
    """Render crawl changes in a compact, actionable form."""
    lines = [
        "Changes:",
        f"- Processed: {report.total}",
        f"- New: {len(report.new)}",
        f"- Updated: {len(report.updated)}",
        f"- Unchanged: {len(report.unchanged)}",
    ]
    if report.new:
        lines.append("New issues:")
        lines.extend(f"- {change.key}" for change in report.new)
    if report.updated:
        lines.append("Updated issues:")
        for change in report.updated:
            details = ", ".join(change.fields) or "content changed"
            if change.differences:
                details = ", ".join(
                    f"{field} ({before} -> {after})"
                    for field, before, after in change.differences
                )
            lines.append(f"- {change.key}: {details}")
    return "\n".join(lines)


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
            print(format_change_report(engine.report))
            print(f"Metrics: {metrics}")
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
