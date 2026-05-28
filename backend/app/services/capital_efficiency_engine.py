from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade
from app.core.logging import logger
from app.services.edge_reality_engine import EdgeRealityEngine


@dataclass
class CapitalEfficiencyResult:
    score: float
    expectancy: float
    max_drawdown: float
    stability: float
    rank: int = 0
    total_strategies: int = 0


class CapitalEfficiencyEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def compute(self, strategy_name: str) -> CapitalEfficiencyResult:
        edge_engine = EdgeRealityEngine(self.db)
        edge = await edge_engine.compute_edge(strategy_name, days=60)

        if edge.total_trades < 3:
            return CapitalEfficiencyResult(
                score=0.0, expectancy=0.0, max_drawdown=0.0, stability=0.0
            )

        expectancy = edge.expectancy
        max_drawdown = await self._compute_max_drawdown(strategy_name)
        stability = edge.stability_score

        dd_safe = max(max_drawdown, 0.001)
        score = expectancy / dd_safe * stability

        return CapitalEfficiencyResult(
            score=round(score, 6),
            expectancy=round(expectancy, 6),
            max_drawdown=round(max_drawdown, 6),
            stability=round(stability, 6),
        )

    async def rank_all(self) -> dict[str, CapitalEfficiencyResult]:
        from app.models.strategy import StrategyConfigRecord
        result = await self.db.execute(
            select(StrategyConfigRecord).where(StrategyConfigRecord.enabled == True)
        )
        records = list(result.scalars().all())

        results = {}
        for record in records:
            results[record.strategy_name] = await self.compute(record.strategy_name)

        sorted_names = sorted(results.keys(), key=lambda n: results[n].score, reverse=True)
        total = len(sorted_names)
        for rank, name in enumerate(sorted_names, 1):
            results[name].rank = rank
            results[name].total_strategies = total

        return results

    async def _compute_max_drawdown(self, strategy_name: str) -> float:
        cutoff = datetime.now(timezone.utc) - timedelta(days=60)
        trades = await self.db.execute(
            select(Trade)
            .where(
                Trade.agent_id == strategy_name,
                Trade.status == "closed",
                Trade.exit_timestamp >= cutoff,
                Trade.pnl.isnot(None),
            )
            .order_by(Trade.exit_timestamp.asc())
        )
        trades = list(trades.scalars().all())

        if not trades:
            return 0.0

        cumulative = 0
        peak = 0
        max_dd = 0
        for t in trades:
            cumulative += float(t.pnl or 0)
            if cumulative > peak:
                peak = cumulative
            dd = (peak - cumulative) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        return max_dd
