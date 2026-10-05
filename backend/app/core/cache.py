"""Cache decorators for API endpoints."""
from functools import wraps
import hashlib
import json
from typing import Any, Callable

from app.core.redis import cache_manager
from app.core.config import settings


def cache_response(ttl: int = None):
    """Decorator to cache API responses in Redis.
    
    Args:
        ttl: Time-to-live in seconds (default from settings)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [func.__qualname__]
            for k, v in sorted(kwargs.items()):
                if v is not None:
                    key_parts.append(f"{k}={v}")
            cache_key = "cache:" + hashlib.sha256("|".join(key_parts).encode()).hexdigest()[:32]
            
            # Try cache
            cached = await cache_manager.get(cache_key)
            if cached is not None:
                return cached
            
            # Call function
            result = await func(*args, **kwargs)
            
            # Store in cache
            if settings.ENABLE_CACHE and ttl:
                await cache_manager.set(cache_key, result, ttl=ttl)
            
            return result
        return wrapper
    return decorator


async def invalidate_cache(pattern: str = None):
    """Invalidate cache entries matching pattern using Redis SCAN."""
    from app.core.redis import cache_manager
    if not settings.ENABLE_CACHE:
        return
    
    client = await cache_manager.get_client()
    if not client:
        return
    
    try:
        if pattern:
            # Use SCAN to find matching keys (safe for production)
            cursor = 0
            while True:
                cursor, keys = await client.scan(cursor, match=f"cache:{pattern}*", count=100)
                if keys:
                    await client.delete(*keys)
                if cursor == 0:
                    break
        else:
            # Clear all cache keys
            cursor = 0
            while True:
                cursor, keys = await client.scan(cursor, match="cache:*", count=100)
                if keys:
                    await client.delete(*keys)
                if cursor == 0:
                    break
    except Exception as e:
        logger.warning("Cache invalidation failed", error=str(e))


def invalidate_on_mutation(pattern: str = None):
    """Decorator to invalidate cache after mutation."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            await invalidate_cache(pattern)
            return result
        return wrapper
    return decorator
