from fastapi import APIRouter

from app.redis import get_redis
from app.core.logging import logger

router = APIRouter()


@router.get("/redis")
async def get_redis_status():
    r = await get_redis()
    info = await r.info("memory")
    keyspace = await r.info("keyspace")

    used_mb = info["used_memory"] / 1024 / 1024
    peak_mb = info["used_memory_peak"] / 1024 / 1024
    max_mb = info.get("maxmemory", 536870912) / 1024 / 1024
    pct = (used_mb / max_mb * 100) if max_mb > 0 else 0

    db0 = keyspace.get("db0", {})
    if isinstance(db0, dict):
        keys_total = int(db0.get("keys", 0))
        expires = int(db0.get("expires", 0))
        avg_ttl = float(db0.get("avg_ttl", 0))
    else:
        keys_total = 0
        expires = 0
        avg_ttl = 0.0

    return {
        "used_memory_mb": round(used_mb, 1),
        "peak_memory_mb": round(peak_mb, 1),
        "maxmemory_mb": round(max_mb, 1),
        "utilization_percent": round(pct, 1),
        "key_count": keys_total,
        "keys_with_expiry": expires,
        "avg_ttl_seconds": round(avg_ttl, 0),
    }
