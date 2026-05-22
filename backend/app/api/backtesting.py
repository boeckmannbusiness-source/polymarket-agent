import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.backtest_service import BacktestService
from app.strategies import get_strategy_names

router = APIRouter()


@router.post("/runs")
async def create_backtest(
    name: str = Query(default="", description="Human-readable name"),
    strategies: list[str] = Query(default=["whale_following"], description="Strategy names"),
    start_days: int = Query(default=7, ge=1, le=365, description="Days of history to test"),
    end_days: int = Query(default=0, ge=0, description="Days ago to end (0 = today)"),
    initial_capital: float = Query(default=10000.0, ge=100, description="Starting capital"),
    mode: str = Query(default="signal_only", pattern="^(signal_only|paper_execution|full_simulation)$"),
    config: str = Query(default="{}", description="JSON strategy config override"),
    db: AsyncSession = Depends(get_db),
):
    import json
    try:
        parsed_config = json.loads(config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in config parameter")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=start_days)
    if end_days > 0:
        end = end - timedelta(days=end_days)

    strategy_cfg = {
        "strategies": strategies,
        "mode": mode,
        "config": parsed_config,
    }

    service = BacktestService(db)
    run = await service.create_run(
        name=name or f"Backtest {strategies[0]} {start_days}d",
        strategy_config=strategy_cfg,
        start_date=start,
        end_date=end,
        initial_capital=initial_capital,
    )
    await db.commit()
    return {
        "id": str(run.id),
        "name": run.name,
        "strategies": strategies,
        "start_date": run.start_date.isoformat(),
        "end_date": run.end_date.isoformat(),
        "initial_capital": initial_capital,
        "mode": mode,
        "status": run.status,
        "message": "Backtest created. POST to /backtesting/runs/{id}/execute to run.",
    }


@router.get("/runs")
async def list_backtests(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = BacktestService(db)
    runs = await service.list_runs(skip=skip, limit=limit)
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "status": r.status,
            "strategies": (r.strategy_config or {}).get("strategies", []),
            "mode": r.mode,
            "total_trades": r.total_trades,
            "win_rate": float(r.win_rate) if r.win_rate else None,
            "sharpe_ratio": float(r.sharpe_ratio) if r.sharpe_ratio else None,
            "total_pnl": float(r.total_pnl) if r.total_pnl else None,
            "initial_capital": float(r.initial_capital) if r.initial_capital else None,
            "final_capital": float(r.final_capital) if r.final_capital else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs
    ]


@router.get("/runs/{run_id}")
async def get_backtest(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    service = BacktestService(db)
    run = await service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")

    trades = await service.get_run_trades(run_id)
    return {
        "id": str(run.id),
        "name": run.name,
        "strategy_config": run.strategy_config,
        "start_date": run.start_date.isoformat() if run.start_date else None,
        "end_date": run.end_date.isoformat() if run.end_date else None,
        "initial_capital": float(run.initial_capital) if run.initial_capital else None,
        "final_capital": float(run.final_capital) if run.final_capital else None,
        "total_trades": run.total_trades,
        "win_rate": float(run.win_rate) if run.win_rate else None,
        "sharpe_ratio": float(run.sharpe_ratio) if run.sharpe_ratio else None,
        "sortino_ratio": float(run.sortino_ratio) if run.sortino_ratio else None,
        "calmar_ratio": float(run.calmar_ratio) if run.calmar_ratio else None,
        "max_drawdown": float(run.max_drawdown) if run.max_drawdown else None,
        "expectancy": float(run.expectancy) if run.expectancy else None,
        "profit_factor": float(run.profit_factor) if run.profit_factor else None,
        "total_pnl": float(run.total_pnl) if run.total_pnl else None,
        "mode": run.mode,
        "status": run.status,
        "error_message": run.error_message,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "trade_count": len(trades),
        "trades": [
            {
                "id": t.id,
                "side": t.side,
                "outcome": t.outcome,
                "entry_price": float(t.entry_price) if t.entry_price else None,
                "exit_price": float(t.exit_price) if t.exit_price else None,
                "size": float(t.size),
                "pnl": float(t.pnl) if t.pnl else None,
                "entry_timestamp": t.entry_timestamp.isoformat() if t.entry_timestamp else None,
                "signal_type": t.signal_type,
            }
            for t in trades
        ],
    }


@router.post("/runs/{run_id}/execute")
async def execute_backtest(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    service = BacktestService(db)
    try:
        run = await service.execute_run(run_id)
        await db.commit()
        return {
            "id": str(run.id),
            "status": run.status,
            "total_trades": run.total_trades,
            "win_rate": float(run.win_rate) if run.win_rate else None,
            "sharpe_ratio": float(run.sharpe_ratio) if run.sharpe_ratio else None,
            "sortino_ratio": float(run.sortino_ratio) if run.sortino_ratio else None,
            "calmar_ratio": float(run.calmar_ratio) if run.calmar_ratio else None,
            "max_drawdown": float(run.max_drawdown) if run.max_drawdown else None,
            "expectancy": float(run.expectancy) if run.expectancy else None,
            "profit_factor": float(run.profit_factor) if run.profit_factor else None,
            "total_pnl": float(run.total_pnl) if run.total_pnl else None,
            "final_capital": float(run.final_capital) if run.final_capital else None,
            "error_message": run.error_message,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/runs/{run_id}")
async def delete_backtest(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    service = BacktestService(db)
    deleted = await service.delete_run(run_id)
    await db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return {"message": "Backtest run deleted"}


@router.get("/compare")
async def compare_backtests(
    ids: str = Query(..., description="Comma-separated backtest run IDs"),
    db: AsyncSession = Depends(get_db),
):
    try:
        run_ids = [uuid.UUID(x.strip()) for x in ids.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID in ids parameter")

    service = BacktestService(db)
    results = await service.compare_runs(run_ids)
    return {"runs": results}


@router.get("/strategies")
async def list_backtest_strategies():
    return {"strategies": sorted(get_strategy_names())}


@router.post("/strategies/{strategy_name}/simulate")
async def simulate_strategy(
    strategy_name: str,
    start_days: int = Query(default=7, ge=1, le=365),
    mode: str = Query(default="signal_only", pattern="^(signal_only|paper_execution|full_simulation)$"),
    config: str = Query(default="{}", description="JSON strategy config"),
    db: AsyncSession = Depends(get_db),
):
    import json
    try:
        parsed_config = json.loads(config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in config parameter")

    from app.strategies import get_strategy
    try:
        get_strategy(strategy_name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_name}' not found")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=start_days)

    service = BacktestService(db)
    run = await service.create_run(
        name=f"Simulate {strategy_name} {start_days}d",
        strategy_config={"strategies": [strategy_name], "mode": mode, "config": parsed_config},
        start_date=start,
        end_date=end,
        initial_capital=10000.0,
    )
    run = await service.execute_run(run.id)
    await db.commit()
    return {
        "id": str(run.id),
        "strategy": strategy_name,
        "mode": mode,
        "start_days": start_days,
        "status": run.status,
        "total_trades": run.total_trades,
        "win_rate": float(run.win_rate) if run.win_rate else None,
        "sharpe_ratio": float(run.sharpe_ratio) if run.sharpe_ratio else None,
        "sortino_ratio": float(run.sortino_ratio) if run.sortino_ratio else None,
        "calmar_ratio": float(run.calmar_ratio) if run.calmar_ratio else None,
        "max_drawdown": float(run.max_drawdown) if run.max_drawdown else None,
        "expectancy": float(run.expectancy) if run.expectancy else None,
        "profit_factor": float(run.profit_factor) if run.profit_factor else None,
        "total_pnl": float(run.total_pnl) if run.total_pnl else None,
        "final_capital": float(run.final_capital) if run.final_capital else None,
        "error_message": run.error_message,
    }
