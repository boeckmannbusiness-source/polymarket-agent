import math
import json
from datetime import datetime, timezone
from typing import Any

from app.core.logging import logger
from app.schemas.shadow import StrategyAnalytics
from app.services.shadow.shadow_execution_service import (
    shadow_execution_service,
    ShadowExecution,
)

ANALYTICS_CACHE_PREFIX = "shadow:analytics:cache:"
ANALYTICS_CACHE_TTL = 60


class ShadowAnalyticsService:
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
            data = await r.get(f"{ANALYTICS_CACHE_PREFIX}{key}")
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
            await r.setex(f"{ANALYTICS_CACHE_PREFIX}{key}", ANALYTICS_CACHE_TTL, json.dumps(data, default=str))
        except Exception:
            pass

    def _filter_by_date(
        self, executions: list[ShadowExecution], start: str | None, end: str | None
    ) -> list[ShadowExecution]:
        if not start and not end:
            return executions
        filtered = []
        for e in executions:
            if not e.entry_timestamp:
                continue
            try:
                ts = e.entry_timestamp
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts)
            except (ValueError, TypeError):
                continue
            if start:
                try:
                    start_dt = datetime.fromisoformat(start)
                    if ts < start_dt:
                        continue
                except (ValueError, TypeError):
                    pass
            if end:
                try:
                    end_dt = datetime.fromisoformat(end)
                    if ts > end_dt:
                        continue
                except (ValueError, TypeError):
                    pass
            filtered.append(e)
        return filtered

    def _compute_strategy_analytics(
        self, executions: list[ShadowExecution], strategy: str
    ) -> StrategyAnalytics:
        strat_execs = [e for e in executions if e.strategy == strategy]
        closed = [e for e in strat_execs if e.status == "closed" and e.realized_pnl is not None]
        open_ = [e for e in strat_execs if e.status == "open"]

        total_signals = len(strat_execs)
        executed_signals = total_signals
        closed_positions = len(closed)

        realized_pnls = [e.realized_pnl for e in closed if e.realized_pnl is not None]
        total_realized = sum(realized_pnls) if realized_pnls else 0.0
        unrealized_pnls = [e.unrealized_pnl for e in open_ if e.unrealized_pnl is not None]
        total_unrealized = sum(unrealized_pnls) if unrealized_pnls else 0.0

        win_count = sum(1 for p in realized_pnls if p > 0)
        loss_count = sum(1 for p in realized_pnls if p < 0)
        win_rate = win_count / len(realized_pnls) if realized_pnls else 0.0
        avg_return = total_realized / len(realized_pnls) if realized_pnls else 0.0

        expectancy = (
            (win_count * avg_return - loss_count * abs(avg_return)) / len(realized_pnls)
            if realized_pnls and avg_return != 0
            else 0.0
        )

        n = len(realized_pnls)
        sharpe_ratio = 0.0
        sortino_ratio = 0.0
        if n > 1:
            mean_r = sum(realized_pnls) / n
            variance = sum((p - mean_r) ** 2 for p in realized_pnls) / (n - 1)
            std = math.sqrt(variance) if variance > 0 else 0.0001
            sharpe_ratio = (mean_r / std) * math.sqrt(252)
            downside = [p for p in realized_pnls if p < 0]
            if downside:
                ds_var = sum((p - mean_r) ** 2 for p in downside) / len(downside)
                ds_std = math.sqrt(ds_var) if ds_var > 0 else 0.0001
                sortino_ratio = (mean_r / ds_std) * math.sqrt(252)
            else:
                sortino_ratio = sharpe_ratio if sharpe_ratio > 0 else 10.0

        max_drawdown = 0.0
        if realized_pnls:
            running = 0.0
            peak = -float("inf")
            for p in realized_pnls:
                running += p
                if running > peak:
                    peak = running
                dd = peak - running
                if dd > max_drawdown:
                    max_drawdown = dd
            max_drawdown = min(max_drawdown / (abs(peak) + 0.0001), 1.0) if peak > 0 else 0.0

        profit_factor = 0.0
        gross_profit = sum(p for p in realized_pnls if p > 0)
        gross_loss = abs(sum(p for p in realized_pnls if p < 0))
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = float("inf")

        avg_holding_hours = 0.0
        holding_times = []
        for e in closed:
            if e.entry_timestamp and e.exit_timestamp:
                try:
                    entry = datetime.fromisoformat(e.entry_timestamp)
                    exit_ = datetime.fromisoformat(e.exit_timestamp)
                    hours = (exit_ - entry).total_seconds() / 3600
                    holding_times.append(hours)
                except (ValueError, TypeError):
                    pass
        if holding_times:
            avg_holding_hours = sum(holding_times) / len(holding_times)

        return StrategyAnalytics(
            strategy=strategy,
            total_pnl=round(total_realized + total_unrealized, 4),
            realized_pnl=round(total_realized, 4),
            unrealized_pnl=round(total_unrealized, 4),
            win_rate=round(win_rate, 4),
            avg_return=round(avg_return, 6),
            sharpe_ratio=round(sharpe_ratio, 4),
            sortino_ratio=round(sortino_ratio, 4),
            max_drawdown=round(max_drawdown, 4),
            profit_factor=round(profit_factor, 4) if profit_factor != float("inf") else 0.0,
            expectancy=round(expectancy, 6),
            average_holding_time_hours=round(avg_holding_hours, 2),
            total_signals=total_signals,
            executed_signals=executed_signals,
            closed_positions=closed_positions,
            win_count=win_count,
            loss_count=loss_count,
        )

    async def get_strategy_analytics(
        self, strategy: str, start: str | None = None, end: str | None = None
    ) -> StrategyAnalytics:
        cache_key = f"strategy:{strategy}:{start or ''}:{end or ''}"
        cached = await self._get_cached(cache_key)
        if cached:
            return StrategyAnalytics(**cached)

        await self._load()
        filtered = self._filter_by_date(self._executions, start, end)
        result = self._compute_strategy_analytics(filtered, strategy)
        await self._set_cache(cache_key, result.model_dump())
        return result

    async def get_all_analytics(
        self, start: str | None = None, end: str | None = None
    ) -> list[StrategyAnalytics]:
        cache_key = f"all:{start or ''}:{end or ''}"
        cached = await self._get_cached(cache_key)
        if cached:
            return [StrategyAnalytics(**item) for item in cached]

        await self._load()
        filtered = self._filter_by_date(self._executions, start, end)
        strategies = sorted(set(e.strategy for e in filtered))

        if not strategies:
            results = []
        else:
            results = await asyncio.gather(
                *[self._compute_strategy_analytics(filtered, s) for s in strategies]
            )

        await self._set_cache(cache_key, [r.model_dump() for r in results])
        return results

    async def invalidate_cache(self):
        r = await self._safe_redis()
        if not r:
            return
        try:
            keys = await r.keys(f"{ANALYTICS_CACHE_PREFIX}*")
            if keys:
                await r.delete(*keys)
        except Exception:
            pass


analytics_service = ShadowAnalyticsService()
