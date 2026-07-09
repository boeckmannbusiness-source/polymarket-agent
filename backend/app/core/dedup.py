from datetime import datetime, timezone

from app.config import settings
from app.core.state_store import LRUCache
from app.core.logging import logger


_local_cache = LRUCache(maxsize=settings.DEDUP_MAX_KEYS, ttl=settings.DEDUP_TTL_SECONDS)

_redis_enabled = settings.DEDUP_REDIS_ENABLED and settings.REDIS_ENABLED

if _redis_enabled:
    _redis_cache = None
else:
    _redis_cache = None


async def _redis():
    global _redis_cache
    if not _redis_enabled:
        return None
    if _redis_cache is not None:
        return _redis_cache
    try:
        from app.redis import get_redis
        r = await get_redis()
        if r is not None:
            _redis_cache = r
        return _redis_cache
    except Exception:
        return None


async def is_duplicate_event(event_hash: str) -> bool:
    key = f"{settings.DEDUP_REDIS_PREFIX}:{event_hash}"
    exists = await _local_cache.get(key)
    if exists is not None:
        logger.debug("dedup_cache_hit_local", event_hash=event_hash[:12])
        return True
    if _redis_enabled:
        try:
            r = await _redis()
            if r is not None:
                exists_redis = await r.exists(key)
                if exists_redis:
                    await _local_cache.set(key, "1")
                    return True
        except Exception as e:
            logger.warning("dedup_redis_check_failed", event_hash=event_hash[:12], error=str(e))
    return False


async def mark_event_processed(event_hash: str) -> None:
    key = f"{settings.DEDUP_REDIS_PREFIX}:{event_hash}"
    await _local_cache.set(key, "1")
    if _redis_enabled:
        try:
            r = await _redis()
            if r is not None:
                await r.set(key, "1", ex=settings.DEDUP_TTL_SECONDS)
        except Exception as e:
            logger.warning("dedup_redis_mark_failed", event_hash=event_hash[:12], error=str(e))


async def dedup_size() -> int:
    return await _local_cache.size()


async def dedup_clear() -> int:
    deleted = await _local_cache.clear()
    logger.info("dedup_cache_cleared", deleted=deleted)
    return deleted
