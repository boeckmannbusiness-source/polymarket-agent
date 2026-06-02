import json
import time
from typing import Any

from app.core.logging import logger

try:
    from app.redis import get_redis
except ImportError:
    get_redis = None


class PortfolioCacheService:
    PREFIX = "portfolio:"

    TTL_CONFIG = {
        "snapshot": 15,
        "strategy_kpis": 60,
        "position_view": 10,
        "market_exposure": 15,
        "strategy_pnl_curve": 60,
        "trade_timeline": 30,
    }

    def __init__(self, redis_enabled: bool | None = None):
        self._memory: dict[str, tuple[float, Any]] = {}
        if redis_enabled is not None:
            self._redis_enabled = redis_enabled
        else:
            self._redis_enabled = get_redis is not None

    async def get(self, key: str) -> Any | None:
        cache_key = f"{self.PREFIX}{key}"
        if self._redis_enabled:
            try:
                r = await get_redis()
                data = await r.get(cache_key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning("portfolio_cache_redis_read_failed", key=cache_key, error=str(e))

        entry = self._memory.get(cache_key)
        if entry:
            expires_at, value = entry
            if time.time() < expires_at:
                return value
            del self._memory[cache_key]
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        cache_key = f"{self.PREFIX}{key}"
        if ttl_seconds is None:
            ttl_seconds = self._resolve_ttl(key)

        self._memory[cache_key] = (time.time() + ttl_seconds, value)

        if self._redis_enabled:
            try:
                r = await get_redis()
                await r.setex(cache_key, ttl_seconds, json.dumps(value, default=str))
            except Exception as e:
                logger.warning("portfolio_cache_redis_write_failed", key=cache_key, error=str(e))

    async def invalidate(self, key: str | None = None) -> None:
        if key:
            cache_key = f"{self.PREFIX}{key}"
            self._memory.pop(cache_key, None)
            if self._redis_enabled:
                try:
                    r = await get_redis()
                    await r.delete(cache_key)
                except Exception:
                    pass
        else:
            self._memory.clear()

    async def invalidate_namespace(self, namespace: str) -> None:
        prefix = f"{self.PREFIX}{namespace}:"
        keys_to_remove = [k for k in self._memory if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._memory[k]

    async def invalidate_on_fill(self) -> None:
        await self.invalidate_namespace("snapshot")
        await self.invalidate_namespace("position_view")
        await self.invalidate_namespace("market_exposure")
        await self.invalidate_namespace("strategy_kpis")
        logger.info("portfolio_cache_invalidated_on_fill")

    def _resolve_ttl(self, key: str) -> int:
        for prefix, ttl in self.TTL_CONFIG.items():
            if key.startswith(prefix):
                return ttl
        return 30
