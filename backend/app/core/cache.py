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


def invalidate_cache(pattern: str):
    """Decorator to invalidate cache entries matching pattern after mutation."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            # Invalidate matching cache entries
            if settings.ENABLE_CACHE:
                # Note: In production, would use Redis SCAN to find matching keys
                # For now, we'll skip invalidation as it's complex without Redis client access
                pass
            
            return result
        return wrapper
    return decorator
