import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func, update, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Trade, StrategyAllocationState
from app.core.logging import logger


@dataclass
class AllocatedPosition:
    size: float
    risk_weight: float
    exposure_bucket: str
    confidence_factor: float = 1.0
    regime_factor: float = 1.0
    strategy_expectancy_factor: float = 1.0
    drawdown_factor: float = 1.0
    liquidity_factor: float = 1.0


class PortfolioAllocator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._allocated_capital_per_strategy: dict[str, float] = {}

    async def allocate(
        self,
        signal_confidence: float,
        strategy_name: str,
        market_archetype: str,
        regime: str,
        current_drawdown: float,
        signal_id: str | None = None,
    ) -> AllocatedPosition:
        base_size = settings.PAPER_INITIAL_CAPITAL * (settings.MAX_POSITION_SIZE_PERCENT / 100)

        confidence_factor = self._compute_confidence_factor(signal_confidence)
        regime_factor = self._compute_regime_factor(regime)
        strategy_expectancy_factor = await self._compute_strategy_expectancy_factor(strategy_name)
        drawdown_factor = self._compute_drawdown_factor(current_drawdown)
        liquidity_factor = self._compute_liquidity_factor(market_archetype)

        allocated_size = (
            base_size
            * confidence_factor
            * regime_factor
            * strategy_expectancy_factor
            * drawdown_factor
            * liquidity_factor
        )

        allocated_size = await self._enforce_hard_caps(
            allocated_size, strategy_name, regime
        )

        risk_weight = self._compute_risk_weight(regime, signal_confidence)
        exposure_bucket = self._classify_exposure_bucket(market_archetype)

        self._allocated_capital_per_strategy[strategy_name] = (
            self._allocated_capital_per_strategy.get(strategy_name, 0) + allocated_size
        )
        await self._persist_allocation_state(strategy_name, allocated_size)

        return AllocatedPosition(
            size=round(allocated_size, 4),
            risk_weight=round(risk_weight, 4),
            exposure_bucket=exposure_bucket,
            confidence_factor=round(confidence_factor, 4),
            regime_factor=round(regime_factor, 4),
            strategy_expectancy_factor=round(strategy_expectancy_factor, 4),
            drawdown_factor=round(drawdown_factor, 4),
            liquidity_factor=round(liquidity_factor, 4),
        )

    def _compute_confidence_factor(self, confidence: float) -> float:
        if confidence >= 0.9:
            return 1.0
        elif confidence >= 0.7:
            return 0.8
        elif confidence >= 0.5:
            return 0.5
        else:
            return 0.25

    def _compute_regime_factor(self, regime: str) -> float:
        factors = {
            "crisis": 0.3,
            "normal": 1.0,
            "extreme": 0.6,
            "high_volatility": 0.5,
            "low_volatility": 0.8,
            "momentum": 0.9,
            "mean_reverting": 0.7,
            "illiquid": 0.2,
        }
        return factors.get(regime, 0.5)

    async def _compute_strategy_expectancy_factor(self, strategy_name: str) -> float:
        from app.models.strategy import StrategyPerformanceRecord
        result = await self.db.execute(
            select(StrategyPerformanceRecord)
            .where(StrategyPerformanceRecord.strategy_name == strategy_name)
            .order_by(StrategyPerformanceRecord.calculated_at.desc())
            .limit(1)
        )
        record = result.scalar_one_or_none()
        if record is None:
            return 1.0
        win_rate = float(record.win_rate) if record.win_rate else 0.5
        if win_rate < 0.35:
            return 0.3
        elif win_rate < 0.5:
            return 0.6
        elif win_rate < 0.7:
            return 1.0
        else:
            return 1.2

    def _compute_drawdown_factor(self, drawdown: float) -> float:
        if drawdown <= 0.05:
            return 1.0
        elif drawdown <= 0.10:
            return 0.75
        elif drawdown <= 0.15:
            return 0.5
        elif drawdown <= 0.20:
            return 0.25
        else:
            return 0.0

    def _compute_liquidity_factor(self, market_archetype: str) -> float:
        factors = {
            "high_liquidity": 1.0,
            "medium_liquidity": 0.8,
            "low_liquidity": 0.4,
            "illiquid": 0.1,
        }
        return factors.get(market_archetype, 0.5)

    async def _enforce_hard_caps(self, size: float, strategy_name: str, regime: str) -> float:
        capital = settings.PAPER_INITIAL_CAPITAL

        single_trade_max = capital * 0.10
        if size > single_trade_max:
            size = single_trade_max

        if regime == "crisis":
            current_crisis_exposure = await self._get_current_exposure(regime_filter="crisis")
            crisis_max = capital * 0.15
            if current_crisis_exposure + size > crisis_max:
                size = max(0, crisis_max - current_crisis_exposure)

        strategy_total = self._allocated_capital_per_strategy.get(strategy_name, 0)
        strategy_max = capital * 0.40
        if strategy_total + size > strategy_max:
            size = max(0, strategy_max - strategy_total)

        corr_exposure = await self._get_correlated_exposure()
        corr_max = capital * 0.25
        if corr_exposure + size > corr_max:
            size = max(0, corr_max - corr_exposure)

        return max(0, size)

    async def _get_current_exposure(self, regime_filter: str | None = None) -> float:
        result = await self.db.execute(
            select(func.coalesce(func.sum(Trade.size), 0))
            .where(Trade.status.in_(["pending", "open"]))
        )
        return float(result.scalar() or 0)

    async def _get_correlated_exposure(self) -> float:
        from app.models.portfolio import MarketCorrelation
        result = await self.db.execute(
            select(func.coalesce(func.sum(Trade.size), 0))
            .where(Trade.status.in_(["pending", "open"]))
        )
        total_open = float(result.scalar() or 0)
        corr_count = await self.db.execute(
            select(func.count())
            .select_from(MarketCorrelation)
            .where(MarketCorrelation.correlation_coefficient >= 0.7)
        )
        count = corr_count.scalar() or 0
        if count > 0:
            return total_open * min(count * 0.1, 0.5)
        return 0

    def _compute_risk_weight(self, regime: str, confidence: float) -> float:
        base = 1.0 - confidence
        regime_penalty = {"crisis": 0.3, "high_volatility": 0.2, "illiquid": 0.3}.get(regime, 0)
        return min(1.0, base + regime_penalty)

    def _classify_exposure_bucket(self, market_archetype: str) -> str:
        buckets = {
            "high_liquidity": "core",
            "medium_liquidity": "core",
            "low_liquidity": "satellite",
            "illiquid": "speculative",
        }
        return buckets.get(market_archetype, "core")

    async def get_allocated_capital(self, strategy_name: str | None = None) -> dict[str, float]:
        if not self._allocated_capital_per_strategy:
            await self.restore_from_db()
        if strategy_name:
            return {strategy_name: self._allocated_capital_per_strategy.get(strategy_name, 0)}
        return dict(self._allocated_capital_per_strategy)

    async def _persist_allocation_state(self, strategy_name: str, amount: float):
        total = self._allocated_capital_per_strategy.get(strategy_name, 0)
        stmt = (
            update(StrategyAllocationState)
            .where(StrategyAllocationState.strategy_name == strategy_name)
            .values(allocated_capital=total)
        )
        result = await self.db.execute(stmt)
        if result.rowcount == 0:
            await self.db.execute(
                insert(StrategyAllocationState).values(
                    strategy_name=strategy_name, allocated_capital=total
                )
            )

    async def restore_from_db(self):
        result = await self.db.execute(select(StrategyAllocationState))
        rows = list(result.scalars().all())
        self._allocated_capital_per_strategy = {row.strategy_name: float(row.allocated_capital) for row in rows}

    def reset(self):
        self._allocated_capital_per_strategy = {}
