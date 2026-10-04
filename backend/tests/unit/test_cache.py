"""Redis cache tests."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.cache import cache_response
from app.core.redis import CacheManager


class TestCacheManager:
    @pytest.mark.asyncio
    async def test_get_fallback_when_redis_unavailable(self):
        """When Redis is unavailable, should use in-memory fallback."""
        manager = CacheManager()
        # Mock Redis connection failure
        with patch('app.core.redis.aioredis.from_url') as mock_from_url:
            mock_from_url.side_effect = Exception("Redis unavailable")
            client = await manager.get_client()
            assert client is not None
            # Should be fallback
            assert hasattr(client, 'get')

    @pytest.mark.asyncio
    async def test_set_get_roundtrip_fallback(self):
        """Test basic cache operations with fallback."""
        manager = CacheManager()
        with patch('app.core.redis.aioredis.from_url') as mock_from_url:
            mock_from_url.side_effect = Exception("Redis unavailable")
            client = await manager.get_client()
            await client.set("test_key", "test_value", ex=60)
            val = await client.get("test_key")
            assert val == "test_value"


class TestCacheDecorator:
    @cache_response(ttl=60)
    async def sample_function(self, x: int) -> dict:
        return {"result": x * 2}

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """First call should compute and cache."""
        manager = CacheManager()
        with patch('app.core.redis.aioredis.from_url') as mock_from_url:
            mock_from_url.side_effect = Exception("Redis unavailable")
            await manager.get_client()
            
            result = await self.sample_function(5)
            assert result["result"] == 10
