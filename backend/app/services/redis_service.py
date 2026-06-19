"""
Redis Service — Cache management and session state.
Provides graceful fallback with in-memory dict when Redis is unavailable.
"""

import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)


class RedisService:
    """Redis cache wrapper with in-memory fallback."""

    def __init__(self):
        self._client: Optional[aioredis.Redis] = None
        self._fallback_store: dict = {}
        self._connected = False

    async def connect(self):
        """Initialize Redis connection."""
        try:
            self._client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._client.ping()
            self._connected = True
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory fallback.")
            self._connected = False

    async def get(self, key: str) -> Optional[str]:
        """Get a value from cache."""
        if self._connected:
            try:
                return await self._client.get(key)
            except Exception:
                pass
        return self._fallback_store.get(key)

    async def set(self, key: str, value: str, ex: int = 3600) -> bool:
        """Set a value in cache with optional expiry (seconds)."""
        if self._connected:
            try:
                await self._client.set(key, value, ex=ex)
                return True
            except Exception:
                pass
        self._fallback_store[key] = value
        return True

    async def get_json(self, key: str) -> Optional[dict]:
        """Get and parse a JSON value from cache."""
        raw = await self.get(key)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return None

    async def set_json(self, key: str, value: dict, ex: int = 3600) -> bool:
        """Store a dict as JSON string in cache."""
        return await self.set(key, json.dumps(value, default=str), ex)

    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        if self._connected:
            try:
                await self._client.delete(key)
                return True
            except Exception:
                pass
        self._fallback_store.pop(key, None)
        return True

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()


# Singleton instance
redis_service = RedisService()
