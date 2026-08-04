"""Datasource selection and automatic API fallback."""

import logging

from ..config import AppConfig
from .api import JiraApiDataSource
from .base import JiraDataSource
from .playwright import JiraPlaywrightDataSource

logger = logging.getLogger(__name__)


async def create_data_source(config: AppConfig) -> JiraDataSource:
    """Select API or Playwright according to configured mode."""
    playwright = JiraPlaywrightDataSource(config.browser, config.crawler)
    if config.datasource.mode == "playwright":
        logger.info("Selected datasource: playwright")
        return playwright
    api = JiraApiDataSource(config.datasource.api)
    if config.datasource.mode == "api":
        logger.info("Selected datasource: api")
        return api
    if await api.health_check():
        logger.info("Selected datasource: api")
        return api
    logger.warning("API unavailable; falling back to Playwright")
    await api.close()
    logger.info("Selected datasource: playwright")
    return playwright