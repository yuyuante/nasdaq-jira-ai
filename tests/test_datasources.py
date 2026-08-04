import pytest

from nasdaq_jira.config import AppConfig
from nasdaq_jira.datasources import factory
from nasdaq_jira.datasources.api import JiraApiDataSource
from nasdaq_jira.datasources.playwright import JiraPlaywrightDataSource


def app_config(mode: str) -> AppConfig:
    return AppConfig(
        browser={"headless": False, "timeout_ms": 1000, "storage_state_path": "state.json", "authenticated_selector": "#user", "login_selector": "#login"},
        crawler={"search_url": "https://jira.example.com/issues/?jql=project%20%3D%20TEST", "max_pages": 1, "page_size": 50, "selectors": {"issue": "a", "key": "a", "summary": "a", "next_page": "a"}},
        datasource={"mode": mode, "api": {"base_url": "https://jira.example.com"}},
        database={"path": "data/test.sqlite3"}, logging={"level": "INFO", "file": "logs/test.log", "backup_count": 1},
    )


@pytest.mark.asyncio
async def test_auto_selects_api_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(JiraApiDataSource, "health_check", lambda self: _true())
    source = await factory.create_data_source(app_config("auto"))
    assert isinstance(source, JiraApiDataSource)
    await source.close()


@pytest.mark.asyncio
async def test_auto_falls_back_when_api_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(JiraApiDataSource, "health_check", lambda self: _false())
    source = await factory.create_data_source(app_config("auto"))
    assert isinstance(source, JiraPlaywrightDataSource)


@pytest.mark.asyncio
async def test_manual_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(JiraApiDataSource, "health_check", lambda self: _true())
    assert isinstance(await factory.create_data_source(app_config("api")), JiraApiDataSource)
    assert isinstance(await factory.create_data_source(app_config("playwright")), JiraPlaywrightDataSource)


async def _true() -> bool:
    return True


async def _false() -> bool:
    return False