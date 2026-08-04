"""Application logging setup."""

import logging
from pathlib import Path


def configure_logging(level: str, file_path: Path) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(file_path, encoding="utf-8"),
        ],
        force=True,
    )
