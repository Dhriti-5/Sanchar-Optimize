"""
Redis Cache Client
Handles caching operations
"""

import logging
from typing import Optional, Any
import json

try:
    import redis.asyncio as redis
except ImportError:
    redis = None

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Client for Redis caching operations"""
    
    def __init__(self):
        """Initialize Redis client"""
        self.client = None
        self.available = False
        
        if redis is None:
            logger.warning("redis not installed. Caching will be disabled.")
            return
        
        try:
            # Will connect lazily when first used
            self.client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            self.available = True
            logger.info("Redis client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            self.client = None
            self.available = False
    
    async def get(self, key: str) -> Optional[str]:
        """
        Get value from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        if not self.available:
            return None
        
        try:
            value = await self.client.get(key)
            return value
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None
    
    async def set(self, key: str, value: str, ttl_seconds: Optional[int] = None) -> bool:
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds
            
        Returns:
            True if successful
        """
        if not self.available:
            return False
        
        try:
            if ttl_seconds:
                await self.client.setex(key, ttl_seconds, value)
            else:
                await self.client.set(key, value)
            return True
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
            return False
    
    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value from cache"""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None
    
    async def set_json(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Set JSON value in cache"""
        try:
            json_str = json.dumps(value)
            return await self.set(key, json_str, ttl_seconds)
        except Exception as e:
            logger.error(f"Redis JSON SET error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.available:
            return False
        
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            return False
    
    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
