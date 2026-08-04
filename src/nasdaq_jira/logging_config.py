"""Application logging setup using the standard logging library."""

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)s [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    level: str,
    file_path: Path,
    backup_count: int = 14,
) -> None:
    """Configure console and daily rotating file logging.

    The file handler rotates at local midnight and retains ``backup_count``
    completed daily log files. Calling this function again replaces handlers so
    CLI entry points and tests do not duplicate log output.
    """
    if backup_count < 0:
        raise ValueError("backup_count must be non-negative")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    log_level = getattr(logging, level.upper(), None)
    if not isinstance(log_level, int):
        raise ValueError(f"Unknown logging level: {level}")

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    file_handler = TimedRotatingFileHandler(
        filename=file_path,
        when="midnight",
        interval=1,
        backupCount=backup_count,
        encoding="utf-8",
        delay=True,
    )
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=log_level,
        handlers=[console_handler, file_handler],
        force=True,
    )
