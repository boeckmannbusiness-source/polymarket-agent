import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BacktestRun, BacktestTrade
from app.services.backtest_engine import BacktestEngine


class BacktestService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.engine = BacktestEngine(db)

    async def list_runs(self, skip: int = 0, limit: int = 20) -> list[BacktestRun]:
        result = await self.db.execute(
            select(BacktestRun).order_by(desc(BacktestRun.created_at)).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_run(self, run_id: uuid.UUID) -> BacktestRun | None:
        result = await self.db.execute(select(BacktestRun).where(BacktestRun.id == run_id))
        return result.scalar_one_or_none()

    async def get_run_trades(self, run_id: uuid.UUID, skip: int = 0, limit: int = 100) -> list[BacktestTrade]:
        result = await self.db.execute(
            select(BacktestTrade)
            .where(BacktestTrade.backtest_run_id == run_id)
            .order_by(BacktestTrade.entry_timestamp)
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

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
            status="pending",
        )
        self.db.add(run)
        await self.db.flush()
        return run

    async def execute_run(self, run_id: uuid.UUID) -> BacktestRun:
        run = await self.get_run(run_id)
        if not run:
            raise ValueError(f"BacktestRun {run_id} not found")
        if run.status == "running":
            raise ValueError(f"BacktestRun {run_id} is already running")
        run = await self.engine.execute(run)
        await self.db.flush()
        return run

    async def delete_run(self, run_id: uuid.UUID) -> bool:
        trades = await self.db.execute(
            select(BacktestTrade).where(BacktestTrade.backtest_run_id == run_id)
        )
        for t in trades.scalars().all():
            await self.db.delete(t)
        run = await self.get_run(run_id)
        if run:
            await self.db.delete(run)
            return True
        return False

    async def compare_runs(self, run_ids: list[uuid.UUID]) -> list[dict[str, Any]]:
        results = []
        for rid in run_ids:
            run = await self.get_run(rid)
            if run:
                results.append({
                    "id": str(run.id),
                    "name": run.name,
                    "strategy_config": run.strategy_config,
                    "total_trades": run.total_trades,
                    "win_rate": float(run.win_rate) if run.win_rate else None,
                    "sharpe_ratio": float(run.sharpe_ratio) if run.sharpe_ratio else None,
                    "sortino_ratio": float(run.sortino_ratio) if run.sortino_ratio else None,
                    "calmar_ratio": float(run.calmar_ratio) if run.calmar_ratio else None,
                    "max_drawdown": float(run.max_drawdown) if run.max_drawdown else None,
                    "expectancy": float(run.expectancy) if run.expectancy else None,
                    "profit_factor": float(run.profit_factor) if run.profit_factor else None,
                    "total_pnl": float(run.total_pnl) if run.total_pnl else None,
                    "initial_capital": float(run.initial_capital) if run.initial_capital else None,
                    "final_capital": float(run.final_capital) if run.final_capital else None,
                    "mode": run.mode,
                    "status": run.status,
                })
        return results
