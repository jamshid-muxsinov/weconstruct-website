"""
Утилиты для работы с кэшем.
"""
from typing import Dict, Any
from src.core.cache import cache_manager
from src.core.db import async_session_factory
from src.services import shop_service

async def clear_product_cache(product_id: int = None):
    """Очистка кэша, связанного с продуктами."""
    patterns = [
        "product_modal",
        "categories_with_products",
        "translation_Product"
    ]
    if product_id:
        patterns.append(f"translation_Product_{product_id}")
    
    for pattern in patterns:
        await cache_manager.clear_pattern(pattern)

async def clear_category_cache(category_id: int = None):
    """Очистка кэша, связанного с категориями."""
    patterns = [
        "categories_with_products",
        "translation_Category"
    ]
    if category_id:
        patterns.append(f"translation_Category_{category_id}")
    
    for pattern in patterns:
        await cache_manager.clear_pattern(pattern)

async def clear_translation_cache():
    """Очистка всего кэша переводов."""
    await cache_manager.clear_pattern("translation_")

async def clear_http_cache():
    """Очистка кэша HTTP ответов."""
    await cache_manager.clear_pattern("http_response")

async def get_cache_stats() -> Dict[str, Any]:
    """Получение статистики кэша."""
    try:
        if cache_manager.is_redis_available and cache_manager.redis_client:
            info = await cache_manager.redis_client.info()
            keys_count = await cache_manager.redis_client.dbsize()
            return {
                "redis_available": True,
                "total_keys": keys_count,
                "memory_usage": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "uptime": info.get("uptime_in_seconds", 0)
            }
        else:
            return {
                "redis_available": False,
                "memory_cache_size": len(cache_manager.memory_cache),
                "lru_cache_size": len(cache_manager.lru_cache)
            }
    except Exception as e:
        return {"error": str(e), "redis_available": False}

async def warm_up_cache():
    """Прогрев кэша: предзагрузка часто используемых данных при старте."""
    try:
        print("🔥 Warming up cache...")
        
        await cache_manager.clear_all()
        
        async with async_session_factory() as session:
            print("   - Caching categories and products...")
            await shop_service.get_categories_with_active_products(session)
        
        print("✅ Cache warm-up complete.")
    except Exception as e:
        print(f"❌ Error during cache warm-up: {e}")

async def schedule_cache_cleanup():
    """Периодическая фоновая задача для очистки HTTP кэша."""
    import asyncio
    from datetime import datetime
    
    while True:
        try:
            # Ожидаем 6 часов перед следующей очисткой
            await asyncio.sleep(6 * 60 * 60)
            
            print(f"🕐 Running scheduled cache cleanup: {datetime.now()}")
            await clear_http_cache()
            
        except Exception as e:
            print(f"❌ Error in scheduled cache cleanup: {e}")
            await asyncio.sleep(60)