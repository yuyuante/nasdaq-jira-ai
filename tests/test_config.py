from pathlib import Path

import pytest
from pydantic import ValidationError

from nasdaq_jira.config import load_config

_CONFIG_PATH = Path("config/config.example.yaml")


def test_load_config() -> None:
    config = load_config(_CONFIG_PATH)
    assert config.crawler.max_pages == 10
    assert config.crawler.selectors["issue"]
    assert config.logging.backup_count == 14
    assert config.browser.authenticated_selector


def test_environment_variables_override_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NASDAQ_JIRA_CRAWLER__MAX_PAGES", "3")

    config = load_config(_CONFIG_PATH)

    assert config.crawler.max_pages == 3


def test_dotenv_values_override_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = _CONFIG_PATH.resolve()
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "NASDAQ_JIRA_LOGGING__LEVEL=DEBUG\n", encoding="utf-8"
    )

    config = load_config(config_path)

    assert config.logging.level == "DEBUG"


def test_invalid_yaml_is_rejected_by_pydantic(tmp_path: Path) -> None:
    invalid_config = tmp_path / "invalid.yaml"
    invalid_config.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(invalid_config)
