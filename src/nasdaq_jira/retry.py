"""Small dependency-free async retry utility."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


async def retry_async[T](
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    initial_delay: float = 1.0,
) -> T:
    """Retry an async operation with exponential backoff."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except Exception:
            if attempt == attempts:
                raise
            delay = initial_delay * (2 ** (attempt - 1))
            logger.warning(
                "Operation failed; retry %d/%d in %.1fs", attempt, attempts - 1, delay
            )
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")
