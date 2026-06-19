import math
import asyncio
from typing import Any

from app.core.logging import logger
from app.schemas.tournament import AllocationResult, StrategyAllocation
from app.services.shadow.shadow_execution_service import shadow_execution_service
from app.services.shadow.shadow_analytics_service import analytics_service
from app.services.shadow.shadow_promotion_service import promotion_service

ALLOCATION_CACHE_PREFIX = "shadow:allocation:cache:"
ALLOCATION_CACHE_TTL = 120


class AllocationEngine:
    MODES = ["equal", "sharpe", "risk_parity", "confidence", "hybrid"]

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
            import json
            data = await r.get(f"{ALLOCATION_CACHE_PREFIX}{key}")
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
                f"{ALLOCATION_CACHE_PREFIX}{key}",
                ALLOCATION_CACHE_TTL,
                json.dumps(data, default=str),
            )
        except Exception:
            pass

    def _normalize(self, weights: dict[str, float]) -> dict[str, float]:
        total = sum(weights.values())
        if total <= 0:
            n = len(weights)
            return {k: 1.0 / n for k in weights} if n > 0 else {}
        return {k: v / total for k, v in weights.items()}

    def _equal_weight(self, strategies: list[str]) -> dict[str, float]:
        n = len(strategies)
        if n == 0:
            return {}
        return {s: 1.0 / n for s in strategies}

    async def _sharpe_weight(self, strategies: list[str]) -> dict[str, float]:
        if not strategies:
            return {}
        analytics_list = await asyncio.gather(
            *[analytics_service.get_strategy_analytics(s) for s in strategies]
        )
        weights = {s: max(a.sharpe_ratio, 0.0) + 0.01 for s, a in zip(strategies, analytics_list)}
        return self._normalize(weights)

    async def _risk_parity_weight(self, strategies: list[str]) -> dict[str, float]:
        if not strategies:
            return {}
        analytics_list = await asyncio.gather(
            *[analytics_service.get_strategy_analytics(s) for s in strategies]
        )
        weights = {s: max(a.max_drawdown, 0.01) for s, a in zip(strategies, analytics_list)}
        return self._normalize(weights)

    async def _confidence_weight(self, strategies: list[str]) -> dict[str, float]:
        if not strategies:
            return {}
        promotion_list = await asyncio.gather(
            *[promotion_service.evaluate_strategy(s) for s in strategies]
        )
        weights = {s: max(p.confidence_score, 1.0) for s, p in zip(strategies, promotion_list)}
        return self._normalize(weights)

    async def _hybrid_weight(self, strategies: list[str]) -> dict[str, float]:
        results = await asyncio.gather(
            self._sharpe_weight(strategies),
            self._risk_parity_weight(strategies),
            self._confidence_weight(strategies),
        )
        equal_w = self._equal_weight(strategies)
        weights = {}
        for s in strategies:
            w = (equal_w[s] + results[0][s] + results[1][s] + results[2][s]) / 4.0
            weights[s] = w
        return self._normalize(weights)

    async def compute_allocation(
        self,
        mode: str = "equal",
        total_capital: float = 100000.0,
    ) -> AllocationResult:
        cache_key = f"alloc:{mode}:{total_capital}"
        cached = await self._get_cached(cache_key)
        if cached:
            return AllocationResult(**cached)

        await shadow_execution_service._ensure_redis()
        strategies = sorted(set(e.strategy for e in shadow_execution_service.get_all_executions()))
        if not strategies:
            result = AllocationResult(
                mode=mode,
                allocations=[],
                total_capital=total_capital,
                description="No strategies available",
            )
            return result

        import asyncio

        if mode == "equal":
            raw_weights = self._equal_weight(strategies)
            desc = "Equal allocation across all strategies"
        elif mode == "sharpe":
            raw_weights = await self._sharpe_weight(strategies)
            desc = "Allocation proportional to Sharpe ratio"
        elif mode == "risk_parity":
            raw_weights = await self._risk_parity_weight(strategies)
            desc = "Allocation inversely proportional to drawdown risk"
        elif mode == "confidence":
            raw_weights = await self._confidence_weight(strategies)
            desc = "Allocation proportional to promotion confidence score"
        elif mode == "hybrid":
            raw_weights = await self._hybrid_weight(strategies)
            desc = "Equal blend of equal, Sharpe, risk parity, and confidence weights"
        else:
            raw_weights = self._equal_weight(strategies)
            desc = f"Unknown mode '{mode}', using equal weight"

        allocations = []
        for s in strategies:
            pct = round(raw_weights.get(s, 0.0) * 100, 2)
            capital = round(raw_weights.get(s, 0.0) * total_capital, 2)
            analytics = await analytics_service.get_strategy_analytics(s)
            risk_score = round(min(analytics.max_drawdown * 5, 1.0), 4)
            allocations.append(
                StrategyAllocation(
                    strategy=s,
                    allocation_pct=pct,
                    capital_assigned=capital,
                    risk_score=risk_score,
                )
            )

        result = AllocationResult(
            mode=mode,
            allocations=allocations,
            total_capital=total_capital,
            description=desc,
        )
        await self._set_cache(cache_key, result.model_dump())
        return result

    async def get_all_modes(self, total_capital: float = 100000.0) -> list[AllocationResult]:
        results = []
        for mode in self.MODES:
            result = await self.compute_allocation(mode, total_capital)
            results.append(result)
        return results


allocation_engine = AllocationEngine()
