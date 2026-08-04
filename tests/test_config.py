from pathlib import Path

from nasdaq_jira.config import load_config


def test_load_config() -> None:
    config = load_config(Path("config/config.example.yaml"))
    assert config.crawler.max_pages == 10
    assert config.crawler.selectors["issue"]
