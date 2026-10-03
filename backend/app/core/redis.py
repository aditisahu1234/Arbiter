import json
import time
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("redis")


class InMemoryCacheFallback:
    """Thread-safe in-memory cache fallback when Redis instance is unreachable."""

    def __init__(self):
        self._store: dict[str, tuple[str, float]] = {}

    async def get(self, key: str) -> str | None:
        if key in self._store:
            val, expire_at = self._store[key]
            if expire_at == 0 or expire_at > time.time():
                return val
            else:
                del self._store[key]
        return None

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        expire_at = (time.time() + ex) if ex else 0.0
        self._store[key] = (value, expire_at)
        return True

    async def delete(self, key: str) -> int:
        if key in self._store:
            del self._store[key]
            return 1
        return 0

    async def ping(self) -> bool:
        return True


class CacheManager:
    """Manages Redis connection with graceful in-memory fallback."""

    def __init__(self):
        self._redis: aioredis.Redis | None = None
        self._fallback = InMemoryCacheFallback()
        self._use_fallback = False

    async def get_client(self):
        if self._use_fallback:
            return self._fallback

        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=1.0,
                )
                await self._redis.ping()
                logger.info("Connected to Redis successfully.")
            except Exception as e:
                logger.warning("Redis unavailable; using in-memory cache fallback", error=str(e))
                self._use_fallback = True
                return self._fallback
        return self._redis

    async def get(self, key: str) -> Any | None:
        client = await self.get_client()
        try:
            val = await client.get(key)
            if val is not None:
                try:
                    return json.loads(val)
                except Exception:
                    return val
            return None
        except Exception as e:
            logger.warning("Cache GET failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        client = await self.get_client()
        ttl = ttl or settings.CACHE_DEFAULT_TTL_SECONDS
        try:
            val_str = json.dumps(value) if not isinstance(value, str) else value
            await client.set(key, val_str, ex=ttl)
            return True
        except Exception as e:
            logger.warning("Cache SET failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        client = await self.get_client()
        try:
            await client.delete(key)
            return True
        except Exception as e:
            logger.warning("Cache DELETE failed", key=key, error=str(e))
            return False


cache_manager = CacheManager()
