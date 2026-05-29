from datetime import datetime, timezone

from app.config import settings
from app.redis import get_redis
from app.core.logging import logger


async def is_duplicate_event(event_hash: str) -> bool:
    if not settings.DEDUP_REDIS_ENABLED:
        return False
    try:
        r = await get_redis()
        key = f"{settings.DEDUP_REDIS_PREFIX}:{event_hash}"
        exists = await r.exists(key)
        if exists:
            logger.debug("dedup_cache_hit", event_hash=event_hash[:12])
        return bool(exists)
    except Exception as e:
        logger.error("dedup_check_failed", event_hash=event_hash[:12], error=str(e))
        return False


async def mark_event_processed(event_hash: str) -> None:
    if not settings.DEDUP_REDIS_ENABLED:
        return
    try:
        r = await get_redis()
        key = f"{settings.DEDUP_REDIS_PREFIX}:{event_hash}"
        await r.setex(key, settings.DEDUP_TTL_SECONDS, "1")
    except Exception as e:
        logger.error("dedup_mark_failed", event_hash=event_hash[:12], error=str(e))


async def dedup_size() -> int:
    try:
        r = await get_redis()
        count = 0
        cursor = 0
        pattern = f"{settings.DEDUP_REDIS_PREFIX}:*"
        while True:
            cursor, keys = await r.scan(cursor=cursor, match=pattern, count=1000)
            count += len(keys)
            if cursor == 0:
                break
        return count
    except Exception:
        return -1


async def dedup_clear() -> int:
    try:
        r = await get_redis()
        pattern = f"{settings.DEDUP_REDIS_PREFIX}:*"
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = await r.scan(cursor=cursor, match=pattern, count=1000)
            if keys:
                await r.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
        logger.info("dedup_cache_cleared", deleted=deleted)
        return deleted
    except Exception as e:
        logger.error("dedup_clear_failed", error=str(e))
        return 0
