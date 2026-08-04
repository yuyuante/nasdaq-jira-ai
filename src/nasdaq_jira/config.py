"""YAML, dotenv, and environment-backed application settings."""

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

_REQUIRED_SELECTORS = {"issue", "key", "summary", "next_page"}


class BrowserConfig(BaseModel):
    """Browser execution settings."""

    headless: bool
    timeout_ms: int = Field(gt=0)
    storage_state_path: Path
    authenticated_selector: str
    login_selector: str


class CrawlerConfig(BaseModel):
    """Jira search and result parsing settings."""

    search_url: str = Field(min_length=1)
    max_pages: int = Field(gt=0)
    page_size: int = Field(gt=0)
    selectors: dict[str, str]

    @field_validator("search_url")
    @classmethod
    def validate_search_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("search_url must be an absolute HTTP(S) URL")
        return value

    @field_validator("selectors")
    @classmethod
    def validate_selectors(cls, value: dict[str, str]) -> dict[str, str]:
        missing = _REQUIRED_SELECTORS - value.keys()
        if missing:
            raise ValueError(f"Missing selectors: {', '.join(sorted(missing))}")
        return value


class DatabaseConfig(BaseModel):
    """Database persistence settings."""

    path: Path


class LoggingConfig(BaseModel):
    """Application logging settings."""

    level: str = Field(min_length=1)
    file: Path
    backup_count: int = Field(ge=0)


class AppConfig(BaseSettings):
    """Validated application configuration.

    Values are loaded from YAML by ``load_config``. Environment variables use
    the ``NASDAQ_JIRA_`` prefix and ``__`` for nested fields; they override
    values from YAML and `.env` values override YAML as well.
    """

    model_config = SettingsConfigDict(
        env_prefix="NASDAQ_JIRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    browser: BrowserConfig
    crawler: CrawlerConfig
    database: DatabaseConfig
    logging: LoggingConfig

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Give process environment and dotenv values precedence over YAML."""
        return (
            env_settings,
            dotenv_settings,
            init_settings,
            file_secret_settings,
        )


def load_config(path: Path) -> AppConfig:
    """Load YAML and validate the merged configuration with Pydantic."""
    with path.open(encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise ValueError("Configuration root must be a YAML mapping")
    return AppConfig(**raw)
