import math
from typing import Any
from datetime import datetime, timezone, timedelta

from app.core.logging import logger
from app.schemas.tournament import (
    SimulationResult,
    SimulatorPoint,
    StrategyContribution,
    TournamentRanking,
)
from app.services.shadow.shadow_execution_service import (
    shadow_execution_service,
    ShadowExecution,
)
from app.services.shadow.strategy_tournament_service import tournament_service
from app.services.shadow.allocation_engine import allocation_engine

SIMULATOR_CACHE_PREFIX = "shadow:simulator:cache:"
SIMULATOR_CACHE_TTL = 120


class PortfolioSimulator:
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
            data = await r.get(f"{SIMULATOR_CACHE_PREFIX}{key}")
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
                f"{SIMULATOR_CACHE_PREFIX}{key}",
                SIMULATOR_CACHE_TTL,
                json.dumps(data, default=str),
            )
        except Exception:
            pass

    async def simulate(
        self,
        starting_capital: float = 100000.0,
        mode: str = "equal",
    ) -> SimulationResult:
        cache_key = f"sim:{mode}:{starting_capital}"
        cached = await self._get_cached(cache_key)
        if cached:
            return SimulationResult(**cached)

        await shadow_execution_service._ensure_redis()
        all_execs = shadow_execution_service.get_all_executions()
        strategies = sorted(set(e.strategy for e in all_execs))
        if not strategies:
            result = SimulationResult(
                starting_capital=starting_capital,
                final_equity=starting_capital,
                total_return=0.0,
                total_return_pct=0.0,
                cagr=0.0,
                volatility=0.0,
                sharpe=0.0,
                calmar_ratio=0.0,
                profit_factor=0.0,
                recovery_factor=0.0,
                max_drawdown=0.0,
                max_drawdown_pct=0.0,
                equity_curve=[],
                strategy_contributions=[],
            )
            return result

        rankings = await tournament_service.get_rankings()
        allocation = await allocation_engine.compute_allocation(mode, starting_capital)

        alloc_map = {}
        for a in allocation.allocations:
            alloc_map[a.strategy] = a.capital_assigned

        strategy_pnls: dict[str, list[float]] = {}
        for s in strategies:
            strat_execs = [e for e in all_execs if e.strategy == s]
            pnls: list[float] = []
            for e in sorted(strat_execs, key=lambda x: x.entry_timestamp or ""):
                if e.status == "closed" and e.realized_pnl is not None:
                    pnls.append(e.realized_pnl * alloc_map.get(s, 0) / 1000.0)
                elif e.unrealized_pnl is not None:
                    pnls.append(e.unrealized_pnl * alloc_map.get(s, 0) / 1000.0)
            strategy_pnls[s] = pnls

        equity = starting_capital
        equity_curve: list[SimulatorPoint] = []
        peak_equity = starting_capital
        max_dd = 0.0
        step = 0
        max_step = max((len(v) for v in strategy_pnls.values()), default=0)

        for step_idx in range(max_step):
            total_pnl = 0.0
            for s in strategies:
                if step_idx < len(strategy_pnls.get(s, [])):
                    total_pnl += strategy_pnls[s][step_idx]
            equity += total_pnl
            if equity > peak_equity:
                peak_equity = equity
            dd = peak_equity - equity
            dd_pct = dd / peak_equity if peak_equity > 0 else 0.0
            if dd_pct > max_dd:
                max_dd = dd_pct
            equity_curve.append(
                SimulatorPoint(
                    step=step_idx,
                    equity=round(equity, 2),
                    pnl=round(total_pnl, 2),
                    drawdown=round(dd_pct, 6),
                )
            )
            step += 1

        final_equity = equity
        total_return = final_equity - starting_capital
        total_return_pct = total_return / starting_capital if starting_capital > 0 else 0.0

        all_pnls = [p.pnl for p in equity_curve]
        n = len(all_pnls)
        volatility = 0.0
        sharpe = 0.0
        if n > 1:
            mean_pnl = sum(all_pnls) / n
            variance = sum((p - mean_pnl) ** 2 for p in all_pnls) / (n - 1)
            volatility = math.sqrt(variance) if variance > 0 else 0.0001
            sharpe = (mean_pnl / volatility) * math.sqrt(252) if volatility > 0 else 0.0

        cagr = 0.0
        if n > 0:
            years = n / 365.0
            if years > 0 and starting_capital > 0:
                cagr = ((final_equity / starting_capital) ** (1.0 / years)) - 1.0 if final_equity >= 0 else -1.0

        calmar_ratio = cagr / max_dd if max_dd > 0 else 0.0

        gross_profit = sum(p for p in all_pnls if p > 0)
        gross_loss = abs(sum(p for p in all_pnls if p < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (0.0 if gross_profit <= 0 else float("inf"))

        recovery_factor = total_return / max_dd if max_dd > 0 else 0.0

        contributions = []
        total_strat_pnl = sum(sum(v) for v in strategy_pnls.values())
        for s in strategies:
            sp = sum(strategy_pnls.get(s, []))
            contrib_pct = sp / total_strat_pnl if total_strat_pnl != 0 else 0.0
            contributions.append(
                StrategyContribution(
                    strategy=s,
                    contribution_pct=round(contrib_pct * 100, 2),
                    total_pnl=round(sp, 2),
                    trade_count=len(strategy_pnls.get(s, [])),
                )
            )

        result = SimulationResult(
            starting_capital=starting_capital,
            final_equity=round(final_equity, 2),
            total_return=round(total_return, 2),
            total_return_pct=round(total_return_pct, 6),
            cagr=round(cagr, 6),
            volatility=round(volatility, 4),
            sharpe=round(sharpe, 4),
            calmar_ratio=round(calmar_ratio, 4),
            profit_factor=round(profit_factor, 4) if profit_factor != float("inf") else 999.0,
            recovery_factor=round(recovery_factor, 4),
            max_drawdown=round(max_dd, 4),
            max_drawdown_pct=round(max_dd * 100, 2),
            equity_curve=equity_curve,
            strategy_contributions=contributions,
        )
        await self._set_cache(cache_key, result.model_dump())
        return result

    async def invalidate_cache(self):
        r = await self._safe_redis()
        if not r:
            return
        try:
            keys = await r.keys(f"{SIMULATOR_CACHE_PREFIX}*")
            if keys:
                await r.delete(*keys)
        except Exception:
            pass


portfolio_simulator = PortfolioSimulator()
