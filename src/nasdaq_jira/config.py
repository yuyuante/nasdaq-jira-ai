"""YAML, dotenv, and environment-backed application settings."""

from pathlib import Path
from typing import Any, Literal
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
    detail_concurrency: int = Field(gt=0, default=4)
    detail_activity_timeout_ms: int = Field(gt=0, default=10000)
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


class ApiConfig(BaseModel):
    """Jira REST API connection settings."""

    base_url: str = "https://jira.example.com"
    token: str | None = None
    timeout_ms: int = Field(gt=0, default=30000)
    page_size: int = Field(gt=0, default=50)
    retry_attempts: int = Field(gt=0, default=3)
    retry_initial_delay: float = Field(gt=0, default=1.0)


class DatasourceConfig(BaseModel):
    """Runtime datasource selection settings."""

    mode: Literal["auto", "api", "playwright"] = "auto"
    api: ApiConfig = Field(default_factory=ApiConfig)


class SyncConfig(BaseModel):
    """Incremental synchronization settings."""

    mode: Literal["full", "incremental"] = "incremental"
    overlap_hours: int = Field(ge=0, default=6)
    batch_size: int = Field(gt=0, default=50)
    datasource: str = "default"


class RagConfig(BaseModel):
    """Retrieval-augmented generation settings."""

    enabled: bool = True
    embedding_provider: Literal["openai"] = "openai"
    embedding_model: str = "text-embedding-3-small"
    answer_model: str = "gpt-4o-mini"
    api_key: str | None = None
    base_url: str = "https://api.openai.com/v1"
    top_k: int = Field(gt=0, default=8)
    score_threshold: float = Field(ge=0, default=0.75)
    chunk_size: int = Field(gt=0, default=800)
    chunk_overlap: int = Field(ge=0, default=100)


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
    datasource: DatasourceConfig = Field(default_factory=DatasourceConfig)
    sync: SyncConfig = Field(default_factory=SyncConfig)
    rag: RagConfig = Field(default_factory=RagConfig)
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
