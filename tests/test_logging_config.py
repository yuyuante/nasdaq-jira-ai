import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import pytest

from nasdaq_jira.logging_config import configure_logging


def test_configure_logging_creates_console_and_daily_file_handlers(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "logs" / "application.log"
    configure_logging("INFO", log_path, backup_count=7)

    handlers = logging.getLogger().handlers
    file_handlers = [
        handler
        for handler in handlers
        if isinstance(handler, TimedRotatingFileHandler)
    ]

    assert len(handlers) == 2
    assert len(file_handlers) == 1
    assert file_handlers[0].when == "MIDNIGHT"
    assert file_handlers[0].backupCount == 7
    assert handlers[0].formatter is not None
    assert "%(asctime)s" in handlers[0].formatter._fmt

    logging.getLogger("test").info("hello")
    logging.shutdown()
    assert log_path.exists()


def test_configure_logging_rejects_unknown_level(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown logging level"):
        configure_logging("VERBOSE", tmp_path / "application.log")