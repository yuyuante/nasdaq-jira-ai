"""Datasource-specific exceptions."""


class AuthenticationError(RuntimeError):
    """Authentication failed."""


class ApiUnavailableError(RuntimeError):
    """The Jira REST API is unavailable or unsupported."""


class PlaywrightError(RuntimeError):
    """The Playwright data source failed."""


class RateLimitError(RuntimeError):
    """The remote service rate-limited a request."""
