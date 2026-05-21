import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BacktestRun, BacktestTrade, MarketEvent, Trade


class BacktestService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_runs(self, skip: int = 0, limit: int = 20) -> list[BacktestRun]:
        result = await self.db.execute(
            select(BacktestRun).order_by(desc(BacktestRun.created_at)).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_run(self, run_id: uuid.UUID) -> BacktestRun:
        result = await self.db.execute(select(BacktestRun).where(BacktestRun.id == run_id))
        return result.scalar_one_or_none()

    async def create_run(
        self,
        name: str,
        strategy_config: dict,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float = 10000.0,
    ) -> BacktestRun:
        run = BacktestRun(
            id=uuid.uuid4(),
            name=name,
            strategy_config=strategy_config,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            status="running",
        )
        self.db.add(run)
        await self.db.flush()
        return run

    async def run_backtest(self, run_id: uuid.UUID):
        run = await self.get_run(run_id)
        if not run:
            return

        capital = float(run.initial_capital or 10000.0)
        trades: list[BacktestTrade] = []
        pnls: list[float] = []

        events = await self.db.execute(
            select(MarketEvent)
            .where(MarketEvent.timestamp.between(run.start_date, run.end_date))
            .order_by(MarketEvent.timestamp)
        )
        market_events = list(events.scalars().all())

        for event in market_events:
            if event.event_type == "trade" and event.price and event.size:
                trade = BacktestTrade(
                    backtest_run_id=run_id,
                    market_id=event.market_id,
                    side="buy" if event.taker_address else "sell",
                    outcome=event.outcome or "unknown",
                    entry_price=float(event.price),
                    size=float(event.size),
                    entry_timestamp=event.timestamp,
                    metadata={"event_id": event.id},
                )
                trades.append(trade)

        win_count = sum(1 for t in trades if t.pnl and t.pnl > 0)
        loss_count = sum(1 for t in trades if t.pnl and t.pnl <= 0)
        total_trades = len(trades)
        win_rate = win_count / total_trades if total_trades > 0 else 0

        if pnls:
            avg_pnl = sum(pnls) / len(pnls)
            import math
            variance = sum((p - avg_pnl) ** 2 for p in pnls) / len(pnls)
            std_dev = math.sqrt(variance) if variance > 0 else 1e-10
            sharpe = (avg_pnl / std_dev) * math.sqrt(252) if std_dev > 0 else 0
        else:
            sharpe = 0

        run.final_capital = capital + sum(pnls)
        run.total_trades = total_trades
        run.win_rate = win_rate
        run.sharpe_ratio = sharpe
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)

        for bt in trades:
            self.db.add(bt)
        await self.db.flush()
