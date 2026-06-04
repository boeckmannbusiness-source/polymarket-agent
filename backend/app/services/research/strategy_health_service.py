import json
from datetime import datetime, timezone, timedelta
from typing import Any

from app.core.logging import logger
from app.schemas.research import StrategyHealth
from app.services.shadow.shadow_execution_service import shadow_execution_service, ShadowExecution
from app.services.shadow.strategy_tournament_service import tournament_service

HEALTH_CACHE_PREFIX = "research:health:cache:"
HEALTH_CACHE_TTL = 60
HEALTH_HISTORY_PREFIX = "research:health:history:"
HEALTH_HISTORY_MAXLEN = 100


class StrategyHealthService:
    async def _safe_redis(self):
        try:
            from app.redis import get_redis
            return await get_redis()
        except Exception:
            return None

    async def _get_cached(self, key: str) -> dict[str, Any] | None:
        r = await self._safe_redis()
        if not r:
            return None
        try:
            data = await r.get(f"{HEALTH_CACHE_PREFIX}{key}")
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    async def _set_cache(self, key: str, data: dict[str, Any]):
        r = await self._safe_redis()
        if not r:
            return
        try:
            await r.setex(f"{HEALTH_CACHE_PREFIX}{key}", HEALTH_CACHE_TTL, json.dumps(data, default=str))
        except Exception:
            pass

    async def _save_history(self, strategy: str, score: float):
        r = await self._safe_redis()
        if not r:
            return
        try:
            entry = json.dumps({"score": score, "timestamp": datetime.now(timezone.utc).isoformat()})
            await r.rpush(f"{HEALTH_HISTORY_PREFIX}{strategy}", entry)
            await r.ltrim(f"{HEALTH_HISTORY_PREFIX}{strategy}", -HEALTH_HISTORY_MAXLEN, -1)
        except Exception:
            pass

    async def _load_history(self, strategy: str, days: int) -> list[float]:
        r = await self._safe_redis()
        if not r:
            return []
        try:
            data = await r.lrange(f"{HEALTH_HISTORY_PREFIX}{strategy}", 0, -1)
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            scores = []
            for item in data:
                try:
                    parsed = json.loads(item)
                    ts = datetime.fromisoformat(parsed["timestamp"])
                    if ts >= cutoff:
                        scores.append(parsed["score"])
                except Exception:
                    pass
            return scores
        except Exception:
            return []

    async def compute_health(self, strategy: str) -> StrategyHealth:
        cache_key = f"health:{strategy}"
        cached = await self._get_cached(cache_key)
        if cached:
            return StrategyHealth(**cached)

        await shadow_execution_service._ensure_redis()
        execs = shadow_execution_service.get_executions_by_strategy(strategy)

        window = await tournament_service.get_window_metrics(strategy)

        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        cutoff_30d = now - timedelta(days=30)
        recent_execs = []
        old_execs = []
        for e in execs:
            if e.entry_timestamp:
                try:
                    ts = datetime.fromisoformat(e.entry_timestamp)
                    if ts >= cutoff_30d:
                        recent_execs.append(e)
                    else:
                        old_execs.append(e)
                except (ValueError, TypeError):
                    pass

        pnls_30d = [e.realized_pnl for e in recent_execs if e.status == "closed" and e.realized_pnl is not None]
        pnls_old = [e.realized_pnl for e in old_execs if e.status == "closed" and e.realized_pnl is not None]
        pnl_recent = sum(pnls_30d) if pnls_30d else 0.0
        pnl_old = sum(pnls_old) if pnls_old else 0.0

        pnl_trend = 0.0
        if abs(pnl_old) > 0.0001:
            pnl_trend = (pnl_recent - pnl_old) / abs(pnl_old)
        elif pnl_recent > 0:
            pnl_trend = 1.0
        elif pnl_recent < 0:
            pnl_trend = -1.0

        wr_30d = window.win_rate_30d
        wr_lifetime = window.win_rate_lifetime
        wr_trend = wr_30d - wr_lifetime if wr_lifetime > 0 else 0.0

        drawdown_trend = 0.0

        score = 100.0
        reason_flags: list[str] = []

        if pnl_trend < -0.3:
            score -= 20
            reason_flags.append("pnl_decline")
        elif pnl_trend < -0.1:
            score -= 10

        if wr_trend < -0.1:
            score -= 15
            reason_flags.append("win_rate_decline")
        elif wr_trend < -0.05:
            score -= 5

        if window.sharpe_30d < 0:
            score -= 10
            reason_flags.append("negative_sharpe")
        if window.sharpe_30d < -1:
            score -= 10

        score = max(0, min(score, 100))

        level = "HEALTHY"
        if score < 50:
            level = "CRITICAL"
        elif score < 75:
            level = "WARNING"

        result = StrategyHealth(
            strategy=strategy,
            score=round(score, 1),
            level=level,
            pnl_trend=round(pnl_trend, 4),
            drawdown_trend=round(drawdown_trend, 4),
            win_rate_trend=round(wr_trend, 4),
            history_7d=await self._load_history(strategy, 7),
            history_30d=await self._load_history(strategy, 30),
            history_lifetime=await self._load_history(strategy, 365),
        )
        await self._set_cache(cache_key, result.model_dump())
        await self._save_history(strategy, result.score)
        return result

    async def get_all_health(self) -> list[StrategyHealth]:
        await shadow_execution_service._ensure_redis()
        strategies = set(e.strategy for e in shadow_execution_service.get_all_executions())
        results = []
        for s in sorted(strategies):
            h = await self.compute_health(s)
            results.append(h)
        return results

    async def invalidate_cache(self):
        r = await self._safe_redis()
        if not r:
            return
        try:
            keys = await r.keys(f"{HEALTH_CACHE_PREFIX}*")
            if keys:
                await r.delete(*keys)
        except Exception:
            pass


health_service = StrategyHealthService()
