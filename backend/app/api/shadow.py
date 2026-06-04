from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.shadow.shadow_execution_service import shadow_execution_service

router = APIRouter()


@router.get("/executions")
async def list_shadow_executions(
    status: str | None = Query(None, pattern="^(open|closed)$"),
    strategy: str | None = None,
    market_id: str | None = None,
):
    await shadow_execution_service._ensure_redis()
    executions = shadow_execution_service.get_all_executions()
    if status:
        executions = [e for e in executions if e.status == status]
    if strategy:
        executions = [e for e in executions if e.strategy == strategy]
    if market_id:
        executions = [e for e in executions if e.market_id == market_id]
    return {
        "executions": [
            {
                "id": e.id,
                "signal_id": e.signal_id,
                "market_id": e.market_id,
                "strategy": e.strategy,
                "direction": e.direction,
                "outcome": e.outcome,
                "size": e.size,
                "entry_price": e.entry_price,
                "current_price": e.current_price,
                "exit_price": e.exit_price,
                "entry_timestamp": e.entry_timestamp,
                "exit_timestamp": e.exit_timestamp,
                "realized_pnl": e.realized_pnl,
                "unrealized_pnl": e.unrealized_pnl,
                "status": e.status,
                "outcome_resolved": e.outcome_resolved,
                "signal_confidence": e.signal_confidence,
            }
            for e in executions
        ],
        "total": len(executions),
    }


@router.get("/executions/{execution_id}")
async def get_shadow_execution(execution_id: str):
    await shadow_execution_service._ensure_redis()
    execution = shadow_execution_service.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {
        "id": execution.id,
        "signal_id": execution.signal_id,
        "market_id": execution.market_id,
        "strategy": execution.strategy,
        "direction": execution.direction,
        "outcome": execution.outcome,
        "size": execution.size,
        "entry_price": execution.entry_price,
        "current_price": execution.current_price,
        "exit_price": execution.exit_price,
        "entry_timestamp": execution.entry_timestamp,
        "exit_timestamp": execution.exit_timestamp,
        "realized_pnl": execution.realized_pnl,
        "unrealized_pnl": execution.unrealized_pnl,
        "status": execution.status,
        "outcome_resolved": execution.outcome_resolved,
        "signal_confidence": execution.signal_confidence,
    }


@router.post("/sync")
async def sync_shadow_signals(db: AsyncSession = Depends(get_db)):
    await shadow_execution_service._ensure_redis()
    report = await shadow_execution_service.sync_from_signals(db)
    return report


@router.post("/refresh-prices")
async def refresh_shadow_prices(db: AsyncSession = Depends(get_db)):
    await shadow_execution_service._ensure_redis()
    report = await shadow_execution_service.refresh_prices(db)
    return report


@router.get("/strategies")
async def get_shadow_strategies():
    await shadow_execution_service._ensure_redis()
    strategies = shadow_execution_service.get_all_strategy_performance()
    return {"strategies": strategies}


@router.get("/performance")
async def get_shadow_performance():
    await shadow_execution_service._ensure_redis()
    performance = shadow_execution_service.get_overall_performance()
    return performance
