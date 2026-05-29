from collections import defaultdict

from app.redis import get_redis
from app.core.metrics import stream_length, consumer_pending, redis_memory_usage_mb, redis_aof_enabled, dedup_key_count, stream_trim_count, pel_depth
from app.core.dedup import dedup_size
from app.core.logging import logger


class RedisMonitor:
    def __init__(self):
        self._streams = {
            "market:data": ["persistence_bridge", "whale_agent"],
            "wallet:trade": ["signal_agent"],
            "signal:generated": ["risk_agent"],
            "trade:request": ["execution_agent"],
            "agent:event": ["monitoring_agent"],
        }

    async def collect_snapshot(self):
        r = await get_redis()

        for stream, groups in self._streams.items():
            try:
                info = await r.xinfo_stream(stream)
                stream_length.labels(stream=stream).set(info["length"])
            except Exception:
                stream_length.labels(stream=stream).set(-1)

            for group in groups:
                try:
                    pending = await r.xpending(stream, group)
                    pending_count = pending.get("pending", 0) if isinstance(pending, dict) else (pending[0] if isinstance(pending, (list, tuple)) else 0)
                    consumer_pending.labels(stream=stream, consumer_group=group).set(pending_count)
                    pel_depth.labels(stream=stream, group=group).set(pending_count)
                except Exception:
                    consumer_pending.labels(stream=stream, consumer_group=group).set(-1)
                    pel_depth.labels(stream=stream, group=group).set(-1)

        try:
            mem_info = await r.info("memory")
            used = mem_info.get("used_memory", 0)
            redis_memory_usage_mb.set(used / 1024 / 1024)
            maxmem = mem_info.get("maxmemory", 0)
        except Exception:
            pass

        try:
            aof = await r.config_get("appendonly")
            redis_aof_enabled.set(1 if aof.get("appendonly") == "yes" else 0)
        except Exception:
            redis_aof_enabled.set(-1)

        try:
            dk = await dedup_size()
            dedup_key_count.set(dk)
        except Exception:
            pass

    async def record_trim(self, stream: str, trimmed: int):
        if trimmed > 0:
            stream_trim_count.labels(stream=stream).set(trimmed)
            logger.info("stream_trim", stream=stream, count=trimmed)
