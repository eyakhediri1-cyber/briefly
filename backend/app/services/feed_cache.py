"""Cache full job-board API feeds to avoid re-fetching on every query."""

import logging
from typing import Any, Callable, Awaitable

from app.services.redis_service import redis_service

logger = logging.getLogger(__name__)

FEED_TTL_SECONDS = 1800  # 30 minutes


async def get_or_fetch_feed(
    source: str,
    fetch_fn: Callable[[], Awaitable[Any]],
    ttl: int = FEED_TTL_SECONDS,
) -> Any:
    """Return cached feed payload or fetch and cache it."""
    key = f"job_feed:{source}"
    cached = await redis_service.get_json(key)
    if cached is not None:
        logger.info("Feed cache HIT for %s (%d items)", source, len(cached) if isinstance(cached, list) else 0)
        return cached

    data = await fetch_fn()
    if data is not None:
        await redis_service.set_json(key, data, ex=ttl)
        logger.info("Feed cache MISS for %s — stored fresh feed", source)
    return data
