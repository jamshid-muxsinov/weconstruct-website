import json
import hashlib
from typing import Any, Optional, Callable
from functools import wraps
import asyncio
from cachetools import TTLCache, LRUCache
import redis.asyncio as aioredis
from src.core.config import get_settings

settings = get_settings()

memory_cache = TTLCache(maxsize=1000, ttl=300) 
lru_cache = LRUCache(maxsize=500)

class CacheManager:
    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        self.is_redis_available = False
        
    async def init_redis(self):
        """Инициализация Redis соединения."""
        if not settings.CACHE_ENABLED or not settings.REDIS_URL:
            print("⚠️ Redis is disabled by settings. Using in-memory cache only.")
            self.is_redis_available = False
            return

        try:
            self.redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                retry_on_timeout=True,
                health_check_interval=30,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            await self.redis_client.ping()
            print("✅ Redis connection successful.")
            self.is_redis_available = True
        except aioredis.ConnectionError as e:
            print(f"❌ Redis connection failed: {e}. Using in-memory cache only.")
            self.is_redis_available = False
            self.redis_client = None
        except Exception as e:
            print(f"❌ Could not connect to Redis: {e}. Using in-memory cache only.")
            self.is_redis_available = False
            self.redis_client = None
    
    async def _check_redis_health(self) -> bool:
        """Проверка состояния Redis соединения."""
        if not self.is_redis_available or not self.redis_client:
            return False
        try:
            await self.redis_client.ping()
            return True
        except Exception:
            self.is_redis_available = False
            return False
    
    async def close_redis(self):
        """Закрытие Redis соединения."""
        if self.redis_client and self.is_redis_available:
            await self.redis_client.close()
            print("Redis connection closed.")
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Генерация ключа кэша на основе префикса, аргументов и параметров."""
        key_parts = [prefix]
        
        if args:
            key_parts.extend([str(arg) for arg in args])
        
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            key_parts.extend([f"{k}:{v}" for k, v in sorted_kwargs])
        
        key_string = "|".join(key_parts)
        return f"{prefix}:{hashlib.md5(key_string.encode()).hexdigest()}"
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Получение значения из кэша (сначала in-memory, потом Redis)."""
        # Проверяем in-memory кэш
        if key in memory_cache:
            return memory_cache[key]
        
        if key in lru_cache:
            return lru_cache[key]
        
        # Проверяем Redis с проверкой состояния
        if await self._check_redis_health():
            try:
                value_str = await self.redis_client.get(key)
                if value_str:
                    parsed_value = json.loads(value_str)
                    # Кэшируем в памяти для быстрого доступа
                    memory_cache[key] = parsed_value
                    return parsed_value
            except (aioredis.ConnectionError, json.JSONDecodeError) as e:
                print(f"Error getting value from Redis for key '{key}': {e}")
                self.is_redis_available = False
            except Exception as e:
                print(f"Unexpected error getting value from Redis for key '{key}': {e}")
        
        return default
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Установка значения в кэш (in-memory и Redis)."""
        try:
            memory_cache[key] = value
            lru_cache[key] = value
            
            if self.is_redis_available and self.redis_client:
                serialized_value = json.dumps(value, default=str)
                await self.redis_client.set(key, serialized_value, ex=ttl)
            
            return True
        except Exception as e:
            print(f"Error setting value to cache for key '{key}': {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Удаление значения из всех уровней кэша."""
        try:
            memory_cache.pop(key, None)
            lru_cache.pop(key, None)
            
            if self.is_redis_available and self.redis_client:
                await self.redis_client.delete(key)
            
            return True
        except Exception as e:
            print(f"Error deleting key '{key}' from cache: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> bool:
        """Очистка кэша по паттерну (например, 'product:*')."""
        try:
            mem_keys_to_remove = [k for k in memory_cache if k.startswith(pattern)]
            for key in mem_keys_to_remove:
                memory_cache.pop(key, None)
            
            lru_keys_to_remove = [k for k in lru_cache if k.startswith(pattern)]
            for key in lru_keys_to_remove:
                lru_cache.pop(key, None)
            
            if self.is_redis_available and self.redis_client:
                async for key in self.redis_client.scan_iter(f"{pattern}*"):
                    await self.redis_client.delete(key)
            
            print(f"Cache cleared for pattern: {pattern}")
            return True
        except Exception as e:
            print(f"Error clearing cache by pattern '{pattern}': {e}")
            return False
    
    async def clear_all(self) -> bool:
        """Полная очистка всего кэша."""
        try:
            memory_cache.clear()
            lru_cache.clear()
            
            if self.is_redis_available and self.redis_client:
                await self.redis_client.flushdb()
            
            print("All caches cleared.")
            return True
        except Exception as e:
            print(f"Error clearing all caches: {e}")
            return False

cache_manager = CacheManager()

def cache_result(prefix: str, ttl: int = 300):
    """
    Декоратор для кэширования результатов асинхронных функций.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not settings.CACHE_ENABLED:
                return await func(*args, **kwargs)

            cache_key = cache_manager._generate_key(prefix, *args, **kwargs)
            
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            result = await func(*args, **kwargs)
            
            await cache_manager.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator

def invalidate_cache(pattern: str):
    """
    Декоратор для инвалидации (сброса) кэша по паттерну после выполнения функции.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            if settings.CACHE_ENABLED:
                await cache_manager.clear_pattern(pattern)
            
            return result
        return wrapper
    return decorator

async def init_cache():
    """Инициализация кэша при запуске приложения."""
    await cache_manager.init_redis()

async def cleanup_cache():
    """Очистка ресурсов кэша при завершении работы приложения."""
    await cache_manager.close_redis()