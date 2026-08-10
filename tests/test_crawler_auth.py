from pathlib import Path

import pytest

from nasdaq_jira.config import load_config
from nasdaq_jira.crawler import JiraCrawler, SessionExpiredError
from nasdaq_jira.models import JiraIssue


@pytest.mark.asyncio
async def test_crawl_requires_saved_session(tmp_path: Path) -> None:
    config = load_config(Path("config/config.example.yaml"))
    browser = config.browser.model_copy(
        update={"storage_state_path": tmp_path / "missing-storage-state.json"}
    )
    crawler = JiraCrawler(browser, config.crawler)

    with pytest.raises(SessionExpiredError, match="--login"):
        await crawler.crawl()


@pytest.mark.asyncio
async def test_crawl_continues_after_one_issue_enrichment_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = load_config(Path("config/config.example.yaml"))
    browser = config.browser.model_copy(
        update={"storage_state_path": tmp_path / "state.json"}
    )
    crawler = JiraCrawler(browser, config.crawler)

    class FakePage:
        def set_default_timeout(self, timeout_ms: int) -> None:
            pass

        async def close(self) -> None:
            pass

    class FakeContext:
        async def new_page(self) -> FakePage:
            return FakePage()

    async def fake_goto(*args: object, **kwargs: object) -> None:
        pass

    async def fake_parse(page: object, issue: JiraIssue) -> JiraIssue:
        if issue.key == "BAD-1":
            raise RuntimeError("history failed")
        return issue

    monkeypatch.setattr("nasdaq_jira.crawler._goto_detail_page_with_retry", fake_goto)
    monkeypatch.setattr(crawler, "_assert_authenticated", lambda page: _async_none())
    monkeypatch.setattr(crawler._parser, "parse_detail_page", fake_parse)

    issues = await crawler._enrich_issue_batch(
        FakeContext(),
        [
            JiraIssue(key="GOOD-1", source_url="/jira/browse/GOOD-1"),
            JiraIssue(key="BAD-1", source_url="/jira/browse/BAD-1"),
        ],
    )

    assert [issue.key for issue in issues] == ["GOOD-1"]
    assert "Failed to enrich issue=BAD-1: RuntimeError: history failed" in caplog.text

    with pytest.raises(RuntimeError, match="Failed to enrich issue=BAD-1"):
        await crawler._enrich_issue_batch(
            FakeContext(),
            [JiraIssue(key="BAD-1", source_url="/jira/browse/BAD-1")],
            continue_on_error=False,
        )


async def _async_none(*args: object, **kwargs: object) -> None:
    return None
