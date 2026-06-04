import math
from typing import Any

from app.core.logging import logger
from app.schemas.shadow import PromotionResult, PromotionThresholds
from app.services.shadow.shadow_execution_service import shadow_execution_service

PROMOTION_CACHE_PREFIX = "shadow:promotion:cache:"
PROMOTION_CACHE_TTL = 120

DEFAULT_THRESHOLDS = PromotionThresholds()


class ShadowPromotionService:
    def __init__(self):
        self._thresholds: PromotionThresholds = DEFAULT_THRESHOLDS

    def set_thresholds(self, t: PromotionThresholds):
        self._thresholds = t

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
            from redis import RedisError
            import json
            data = await r.get(f"{PROMOTION_CACHE_PREFIX}{key}")
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
            import json
            await r.setex(
                f"{PROMOTION_CACHE_PREFIX}{key}",
                PROMOTION_CACHE_TTL,
                json.dumps(data, default=str),
            )
        except Exception:
            pass

    def _compute_confidence(
        self,
        trade_count: int,
        win_rate: float,
        sharpe: float,
        drawdown: float,
        alpha: float,
    ) -> float:
        score = 0.0
        if trade_count >= self._thresholds.minimum_trades:
            score += 20
        elif trade_count >= self._thresholds.minimum_trades * 0.5:
            score += 10
        else:
            score += 5

        if win_rate >= self._thresholds.minimum_win_rate:
            score += 20
        elif win_rate >= self._thresholds.minimum_win_rate * 0.8:
            score += 10
        else:
            score += 5

        if sharpe >= self._thresholds.minimum_sharpe:
            score += 20
        elif sharpe >= self._thresholds.minimum_sharpe * 0.5:
            score += 10
        else:
            score += 5

        if drawdown <= self._thresholds.maximum_drawdown:
            score += 20
        elif drawdown <= self._thresholds.maximum_drawdown * 1.5:
            score += 10
        else:
            score += 5

        if alpha > 0:
            score += 20
        elif alpha > -1:
            score += 10
        else:
            score += 5

        return min(max(score, 0), 100)

    async def evaluate_strategy(
        self,
        strategy: str,
        analytics: dict[str, Any] | None = None,
        benchmark: dict[str, Any] | None = None,
    ) -> PromotionResult:
        cache_key = f"eval:{strategy}"
        if analytics is None and benchmark is None:
            cached = await self._get_cached(cache_key)
            if cached:
                return PromotionResult(**cached)

        await shadow_execution_service._ensure_redis()
        execs = shadow_execution_service.get_executions_by_strategy(strategy)

        if analytics is None:
            from app.services.shadow.shadow_analytics_service import analytics_service
            analytics_obj = await analytics_service.get_strategy_analytics(strategy)
            analytics = analytics_obj.model_dump()

        if benchmark is None:
            from app.services.shadow.shadow_benchmark_service import benchmark_service
            benchmark_obj = await benchmark_service.get_strategy_benchmark(strategy)
            benchmark = benchmark_obj.model_dump()

        trade_count = analytics.get("closed_positions", 0) + analytics.get("executed_signals", 0)
        win_rate = analytics.get("win_rate", 0.0)
        sharpe = analytics.get("sharpe_ratio", 0.0)
        drawdown = analytics.get("max_drawdown", 0.0)
        alpha = benchmark.get("alpha", 0.0)
        expectancy = analytics.get("expectancy", 0.0)

        confidence = self._compute_confidence(trade_count, win_rate, sharpe, drawdown, alpha)

        reasons: list[str] = []
        blockers: list[str] = []

        if trade_count >= self._thresholds.minimum_trades:
            reasons.append(f"Sufficient trades ({trade_count} >= {self._thresholds.minimum_trades})")
        else:
            blockers.append(
                f"Insufficient trades ({trade_count} < {self._thresholds.minimum_trades})"
            )

        if win_rate >= self._thresholds.minimum_win_rate:
            reasons.append(f"Win rate {win_rate:.1%} >= {self._thresholds.minimum_win_rate:.0%}")
        else:
            blockers.append(
                f"Win rate too low ({win_rate:.1%} < {self._thresholds.minimum_win_rate:.0%})"
            )

        if sharpe >= self._thresholds.minimum_sharpe:
            reasons.append(f"Sharpe {sharpe:.2f} >= {self._thresholds.minimum_sharpe}")
        else:
            blockers.append(f"Sharpe too low ({sharpe:.2f} < {self._thresholds.minimum_sharpe})")

        if drawdown <= self._thresholds.maximum_drawdown:
            reasons.append(f"Drawdown {drawdown:.1%} <= {self._thresholds.maximum_drawdown:.0%}")
        else:
            blockers.append(
                f"Drawdown too high ({drawdown:.1%} > {self._thresholds.maximum_drawdown:.0%})"
            )

        if expectancy >= self._thresholds.minimum_expectancy:
            reasons.append(f"Expectancy {expectancy:.4f} >= {self._thresholds.minimum_expectancy}")
        else:
            blockers.append(
                f"Expectancy too low ({expectancy:.4f} < {self._thresholds.minimum_expectancy})"
            )

        if alpha > 0:
            reasons.append(f"Positive alpha vs benchmark ({alpha:.4f})")

        has_trade_blocker = any("Insufficient trades" in b for b in blockers)
        if has_trade_blocker:
            recommended_tier = "SHADOW"
        elif confidence >= 80 and len(blockers) == 0:
            recommended_tier = "LIVE"
        elif confidence >= 50 and len(blockers) <= 1:
            recommended_tier = "PAPER"
        else:
            recommended_tier = "SHADOW"

        result = PromotionResult(
            strategy=strategy,
            current_tier="SHADOW",
            recommended_tier=recommended_tier,
            confidence_score=round(confidence, 1),
            reasons=reasons,
            blockers=blockers,
        )

        if analytics is None and benchmark is None:
            await self._set_cache(cache_key, result.model_dump())

        logger.info(
            "shadow_promotion_evaluated",
            strategy=strategy,
            recommended=recommended_tier,
            confidence=confidence,
            blockers=len(blockers),
        )
        return result

    async def evaluate_all(self) -> list[PromotionResult]:
        await shadow_execution_service._ensure_redis()
        strategies = set(e.strategy for e in shadow_execution_service.get_all_executions())
        results = []
        for s in sorted(strategies):
            result = await self.evaluate_strategy(s)
            results.append(result)
        return results

    async def invalidate_cache(self):
        r = await self._safe_redis()
        if not r:
            return
        try:
            keys = await r.keys(f"{PROMOTION_CACHE_PREFIX}*")
            if keys:
                await r.delete(*keys)
        except Exception:
            pass


promotion_service = ShadowPromotionService()
