import json
import random
import math
from datetime import datetime, timezone
from typing import Any

from app.core.logging import logger
from app.schemas.shadow import BenchmarkComparison
from app.services.shadow.shadow_execution_service import (
    shadow_execution_service,
    ShadowExecution,
)

BENCHMARK_CACHE_PREFIX = "shadow:benchmark:cache:"
BENCHMARK_CACHE_TTL = 120
BENCHMARK_SNAPSHOT_KEY = "shadow:benchmark:snapshots"


class ShadowBenchmarkService:
    def __init__(self):
        self._executions: list[ShadowExecution] = []

    async def _load(self):
        await shadow_execution_service._ensure_redis()
        self._executions = shadow_execution_service.get_all_executions()

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
            data = await r.get(f"{BENCHMARK_CACHE_PREFIX}{key}")
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
            await r.setex(
                f"{BENCHMARK_CACHE_PREFIX}{key}", BENCHMARK_CACHE_TTL, json.dumps(data, default=str)
            )
        except Exception:
            pass

    async def _save_snapshot(self, strategy: str, benchmark: dict[str, Any]):
        r = await self._safe_redis()
        if not r:
            return
        try:
            snapshot = {
                **benchmark,
                "strategy": strategy,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await r.rpush(BENCHMARK_SNAPSHOT_KEY, json.dumps(snapshot, default=str))
            await r.ltrim(BENCHMARK_SNAPSHOT_KEY, -100, -1)
        except Exception:
            pass

    def _buy_hold_return(
        self, executions: list[ShadowExecution], outcome_target: str
    ) -> float:
        relevant = [e for e in executions if e.outcome.upper() == outcome_target.upper()]
        if not relevant:
            return 0.0
        returns = []
        for e in relevant:
            if e.status == "closed" and e.realized_pnl is not None:
                returns.append(e.realized_pnl)
            elif e.unrealized_pnl is not None:
                returns.append(e.unrealized_pnl)
        if not returns:
            return 0.0
        return sum(returns)

    def _random_entry_return(self, executions: list[ShadowExecution]) -> float:
        if not executions:
            return 0.0
        if len(executions) < 2:
            e = executions[0]
            if e.status == "closed" and e.realized_pnl is not None:
                return e.realized_pnl
            return e.unrealized_pnl or 0.0
        sample_size = max(1, len(executions) // 3)
        sample = random.Random(42).sample(executions, sample_size)
        total = 0.0
        for e in sample:
            if e.status == "closed" and e.realized_pnl is not None:
                total += e.realized_pnl
            elif e.unrealized_pnl is not None:
                total += e.unrealized_pnl
        return total

    async def get_strategy_benchmark(self, strategy: str) -> BenchmarkComparison:
        cache_key = f"benchmark:{strategy}"
        cached = await self._get_cached(cache_key)
        if cached:
            return BenchmarkComparison(**cached)

        await self._load()
        strat_execs = [e for e in self._executions if e.strategy == strategy]
        if not strat_execs:
            result = BenchmarkComparison(strategy=strategy)
            await self._set_cache(cache_key, result.model_dump())
            return result

        buy_hold_yes = self._buy_hold_return(strat_execs, "YES")
        buy_hold_no = self._buy_hold_return(strat_execs, "NO")
        random_entry = self._random_entry_return(strat_execs)

        strat_realized = [e.realized_pnl for e in strat_execs if e.status == "closed" and e.realized_pnl is not None]
        strategy_return = sum(strat_realized) if strat_realized else 0.0

        benchmark_return = buy_hold_yes + buy_hold_no
        excess_return = strategy_return - benchmark_return
        avg_bench_return = benchmark_return / 2 if benchmark_return != 0 else 0.0001

        strat_returns = strat_realized if strat_realized else [0.0]
        n = len(strat_returns)
        if n > 1:
            mean_r = sum(strat_returns) / n
            variance = sum((p - mean_r) ** 2 for p in strat_returns) / (n - 1)
            strat_std = math.sqrt(variance) if variance > 0 else 0.0001
            tracking_error = abs(strat_std - abs(avg_bench_return)) + 0.0001
            information_ratio = excess_return / tracking_error if tracking_error > 0 else 0.0
        else:
            information_ratio = 0.0

        alpha = excess_return

        result = BenchmarkComparison(
            strategy=strategy,
            alpha=round(alpha, 4),
            excess_return=round(excess_return, 4),
            information_ratio=round(information_ratio, 4),
            buy_hold_yes_return=round(buy_hold_yes, 4),
            buy_hold_no_return=round(buy_hold_no, 4),
            random_entry_return=round(random_entry, 4),
        )
        await self._set_cache(cache_key, result.model_dump())
        await self._save_snapshot(strategy, result.model_dump())
        return result

    async def get_all_benchmarks(self) -> list[BenchmarkComparison]:
        await self._load()
        strategies = set(e.strategy for e in self._executions)
        results = []
        for s in sorted(strategies):
            b = await self.get_strategy_benchmark(s)
            results.append(b)
        return results

    async def invalidate_cache(self):
        r = await self._safe_redis()
        if not r:
            return
        try:
            keys = await r.keys(f"{BENCHMARK_CACHE_PREFIX}*")
            if keys:
                await r.delete(*keys)
        except Exception:
            pass


benchmark_service = ShadowBenchmarkService()
