"""Pluggable Jira data sources."""

from .base import JiraDataSource
from .factory import create_data_source

__all__ = ["JiraDataSource", "create_data_source"]
