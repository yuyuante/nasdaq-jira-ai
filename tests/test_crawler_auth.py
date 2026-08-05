from pathlib import Path

import pytest

from nasdaq_jira.config import load_config
from nasdaq_jira.crawler import JiraCrawler, SessionExpiredError


@pytest.mark.asyncio
async def test_crawl_requires_saved_session(tmp_path: Path) -> None:
    config = load_config(Path("config/config.example.yaml"))
    browser = config.browser.model_copy(
        update={"storage_state_path": tmp_path / "missing-storage-state.json"}
    )
    crawler = JiraCrawler(browser, config.crawler)

    with pytest.raises(SessionExpiredError, match="--login"):
        await crawler.crawl()
