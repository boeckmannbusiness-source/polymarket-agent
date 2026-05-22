from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.strategy import StrategyConfigRecord, StrategyPerformanceRecord


class StrategyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_config(self, strategy_name: str) -> StrategyConfigRecord | None:
        result = await self.db.execute(
            select(StrategyConfigRecord)
            .where(StrategyConfigRecord.strategy_name == strategy_name, StrategyConfigRecord.enabled)
            .order_by(desc(StrategyConfigRecord.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def save_config(self, strategy_name: str, config: dict, version: str = "1.0.0") -> StrategyConfigRecord:
        obj = StrategyConfigRecord(
            strategy_name=strategy_name,
            version=version,
            config=config,
        )
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update_performance(
        self,
        strategy_name: str,
        version: str,
        signal_result: bool,
        pnl: float | None = None,
        confidence: float | None = None,
    ):
        result = await self.db.execute(
            select(StrategyPerformanceRecord)
            .where(
                StrategyPerformanceRecord.strategy_name == strategy_name,
                StrategyPerformanceRecord.version == version,
                StrategyPerformanceRecord.period_end.is_(None),
            )
            .order_by(desc(StrategyPerformanceRecord.calculated_at))
            .limit(1)
        )
        perf = result.scalar_one_or_none()
        if not perf:
            perf = StrategyPerformanceRecord(
                strategy_name=strategy_name,
                version=version,
                period_start=datetime.now(timezone.utc),
            )
            self.db.add(perf)

        perf.total_signals += 1
        if signal_result:
            perf.winning_signals += 1
        else:
            perf.losing_signals += 1
        perf.executed_signals += 1

        if pnl is not None:
            perf.total_pnl = (perf.total_pnl or 0) + pnl
        if confidence is not None:
            total = perf.total_signals
            prev_avg = perf.avg_confidence or 0
            perf.avg_confidence = round((prev_avg * (total - 1) + confidence) / total, 6)

        total = perf.executed_signals
        perf.win_rate = round(perf.winning_signals / total, 6) if total > 0 else None
        await self.db.flush()
        return perf

    async def get_performance(self, strategy_name: str) -> list[StrategyPerformanceRecord]:
        result = await self.db.execute(
            select(StrategyPerformanceRecord)
            .where(StrategyPerformanceRecord.strategy_name == strategy_name)
            .order_by(desc(StrategyPerformanceRecord.calculated_at))
            .limit(50)
        )
        return list(result.scalars().all())
