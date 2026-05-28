import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade
from app.models.strategy import StrategyConfigRecord, StrategyPerformanceRecord
from app.core.logging import logger


@dataclass
class StrategyStatus:
    status: str  # "ACTIVE" | "DISABLED" | "PROBATION"
    reason: str
    metrics_snapshot: dict[str, Any] = field(default_factory=dict)


class StrategyGuardian:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._kill_count = 0
        self._cached_statuses: dict[str, StrategyStatus] = {}

    async def evaluate_strategy(self, strategy_name: str) -> StrategyStatus:
        recent_trades = await self._get_recent_trades(strategy_name, limit=200)
        metrics = await self._compute_metrics(strategy_name, recent_trades)

        if len(recent_trades) < 5:
            status = StrategyStatus(
                status="ACTIVE",
                reason="insufficient_data",
                metrics_snapshot=metrics,
            )
            self._cached_statuses[strategy_name] = status
            return status

        kill_reasons = []

        win_rate = metrics.get("win_rate", 1.0)
        if win_rate < 0.35 and metrics.get("total_trades", 0) >= 50:
            kill_reasons.append(f"win_rate_{win_rate:.2%}_below_35%")

        expectancy = metrics.get("expectancy", 0)
        if expectancy < 0 and metrics.get("total_trades", 0) >= 200:
            kill_reasons.append(f"negative_expectancy_{expectancy:.4f}_over_200_trades")

        consecutive_losses = metrics.get("consecutive_losses", 0)
        if consecutive_losses >= 4:
            kill_reasons.append(f"{consecutive_losses}_consecutive_losses")

        strategy_drawdown = metrics.get("strategy_drawdown", 0)
        if strategy_drawdown > 0.25:
            kill_reasons.append(f"drawdown_{strategy_drawdown:.2%}_exceeds_25%")

        losing_regime_corr = metrics.get("losing_regime_correlation", 0)
        if losing_regime_corr > 0.8:
            kill_reasons.append(f"losing_regime_correlation_{losing_regime_corr:.2f}")

        if kill_reasons:
            self._kill_count += 1
            await self._disable_strategy(strategy_name, kill_reasons)
            status = StrategyStatus(
                status="DISABLED",
                reason="; ".join(kill_reasons),
                metrics_snapshot=metrics,
            )
        elif win_rate < 0.45 and metrics.get("total_trades", 0) >= 20:
            status = StrategyStatus(
                status="PROBATION",
                reason=f"win_rate_{win_rate:.2%}_below_45%_threshold",
                metrics_snapshot=metrics,
            )
        else:
            status = StrategyStatus(
                status="ACTIVE",
                reason="all_checks_passed",
                metrics_snapshot=metrics,
            )

        self._cached_statuses[strategy_name] = status
        return status

    async def evaluate_all(self) -> dict[str, StrategyStatus]:
        result = await self.db.execute(
            select(StrategyConfigRecord).where(StrategyConfigRecord.enabled == True)
        )
        records = list(result.scalars().all())
        results = {}
        for record in records:
            results[record.strategy_name] = await self.evaluate_strategy(record.strategy_name)
        return results

    async def _get_recent_trades(self, strategy_name: str, limit: int = 200) -> list[Trade]:
        result = await self.db.execute(
            select(Trade)
            .where(Trade.agent_id == strategy_name)
            .where(Trade.status == "closed")
            .order_by(Trade.exit_timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _compute_metrics(
        self, strategy_name: str, trades: list[Trade]
    ) -> dict[str, Any]:
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "expectancy": 0,
                "consecutive_losses": 0,
                "strategy_drawdown": 0,
                "losing_regime_correlation": 0,
                "total_pnl": 0,
                "avg_pnl": 0,
            }

        winning = [t for t in trades if t.pnl is not None and t.pnl > 0]
        losing = [t for t in trades if t.pnl is not None and t.pnl <= 0]
        win_rate = len(winning) / len(trades) if trades else 0

        total_pnl = sum(float(t.pnl or 0) for t in trades)
        avg_pnl = total_pnl / len(trades) if trades else 0
        expectancy = total_pnl / max(len(trades), 1)

        consecutive_losses = 0
        max_consecutive = 0
        for t in trades:
            if t.pnl is not None and t.pnl <= 0:
                consecutive_losses += 1
                max_consecutive = max(max_consecutive, consecutive_losses)
            else:
                consecutive_losses = 0

        cumulative = 0
        peak = 0
        dd = 0
        for t in trades:
            cumulative += float(t.pnl or 0)
            if cumulative > peak:
                peak = cumulative
            dd = min(dd, cumulative - peak)
        strategy_drawdown = abs(dd) / abs(peak) if peak != 0 else 0

        losing_regime_corr = await self._compute_losing_regime_correlation(
            strategy_name, losing
        )

        return {
            "total_trades": len(trades),
            "wins": len(winning),
            "losses": len(losing),
            "win_rate": round(win_rate, 6),
            "expectancy": round(expectancy, 6),
            "consecutive_losses": max_consecutive,
            "strategy_drawdown": round(strategy_drawdown, 6),
            "losing_regime_correlation": round(losing_regime_corr, 6),
            "total_pnl": round(total_pnl, 4),
            "avg_pnl": round(avg_pnl, 4),
        }

    async def _compute_losing_regime_correlation(
        self, strategy_name: str, losing_trades: list[Trade]
    ) -> float:
        if len(losing_trades) < 3:
            return 0.0
        from app.models.portfolio import MarketCorrelation
        market_ids = [t.market_id for t in losing_trades if t.market_id]
        if not market_ids:
            return 0.0
        result = await self.db.execute(
            select(func.avg(MarketCorrelation.correlation_coefficient))
            .where(
                (MarketCorrelation.market_a_id.in_(market_ids)) |
                (MarketCorrelation.market_b_id.in_(market_ids))
            )
        )
        avg_corr = result.scalar()
        return float(avg_corr) if avg_corr else 0.0

    async def _disable_strategy(self, strategy_name: str, reasons: list[str]) -> None:
        result = await self.db.execute(
            select(StrategyConfigRecord)
            .where(StrategyConfigRecord.strategy_name == strategy_name)
        )
        record = result.scalar_one_or_none()
        if record:
            record.enabled = False
            record.lifecycle = "DISABLED"
            await self.db.flush()
            logger.warning(
                "strategy_disabled",
                strategy=strategy_name,
                reasons=reasons,
            )

    def get_strategy_status(self, strategy_name: str) -> StrategyStatus | None:
        return self._cached_statuses.get(strategy_name)

    def get_all_statuses(self) -> dict[str, StrategyStatus]:
        return dict(self._cached_statuses)

    def get_kill_count(self) -> int:
        return self._kill_count

    def reset(self):
        self._cached_statuses = {}
        self._kill_count = 0
