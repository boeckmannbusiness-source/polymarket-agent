from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.portfolio_service import PortfolioService
from app.services.strategy_ranking_service import StrategyRankingService

router = APIRouter()


@router.get("/history")
async def get_portfolio_history(hours: int = Query(168, ge=1, le=8760), db: AsyncSession = Depends(get_db)):
    service = PortfolioService(db)
    history = await service.get_portfolio_history(hours=hours)
    return [
        {
            "portfolio_value": float(h.portfolio_value) if h.portfolio_value else 0,
            "total_realized_pnl": float(h.total_realized_pnl) if h.total_realized_pnl else 0,
            "total_unrealized_pnl": float(h.total_unrealized_pnl) if h.total_unrealized_pnl else 0,
            "drawdown": float(h.drawdown) if h.drawdown else 0,
            "timestamp": h.timestamp.isoformat(),
        }
        for h in history
    ]


@router.post("/snapshot")
async def take_portfolio_snapshot(db: AsyncSession = Depends(get_db)):
    service = PortfolioService(db)
    snap = await service.compute_portfolio_snapshot()
    await db.commit()
    return {
        "id": str(snap.id),
        "total_exposure": float(snap.total_exposure),
        "open_positions": snap.open_positions,
        "total_unrealized_pnl": float(snap.total_unrealized_pnl) if snap.total_unrealized_pnl else 0,
        "total_realized_pnl": float(snap.total_realized_pnl) if snap.total_realized_pnl else 0,
        "portfolio_value": float(snap.portfolio_value) if snap.portfolio_value else 0,
        "drawdown": float(snap.drawdown) if snap.drawdown else 0,
        "timestamp": snap.timestamp.isoformat(),
    }


@router.post("/positions")
async def create_position(
    market_condition_id: str,
    direction: str = Query(pattern="^(YES|NO)$"),
    size: float = Query(gt=0),
    entry_price: float = Query(gt=0, le=1),
    strategy_name: str | None = None,
    signal_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioService(db)
    pos = await service.open_position(
        market_condition_id=market_condition_id,
        direction=direction,
        size=size,
        entry_price=entry_price,
        strategy_name=strategy_name,
        signal_id=signal_id,
    )
    await db.commit()
    return {
        "id": str(pos.id),
        "market_condition_id": pos.market_condition_id,
        "direction": pos.direction,
        "size": float(pos.size),
        "entry_price": float(pos.entry_price),
        "status": pos.status,
        "opened_at": pos.opened_at.isoformat(),
    }


@router.post("/positions/{position_id}/close")
async def close_position(position_id: UUID, exit_price: float = Query(gt=0, le=1), db: AsyncSession = Depends(get_db)):
    service = PortfolioService(db)
    pos = await service.close_position(position_id, exit_price)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found or already closed")
    await db.commit()
    return {
        "id": str(pos.id),
        "realized_pnl": float(pos.realized_pnl) if pos.realized_pnl else 0,
        "status": pos.status,
        "closed_at": pos.closed_at.isoformat() if pos.closed_at else None,
    }


@router.get("/correlations")
async def get_correlations(
    threshold: float = Query(default=0.3, ge=0, le=1),
    recalculate: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioService(db)
    if recalculate:
        await service.compute_correlations()
        await db.commit()
    return await service.get_correlations(threshold=threshold)


@router.get("/rankings")
async def get_strategy_rankings(db: AsyncSession = Depends(get_db)):
    service = StrategyRankingService(db)
    return await service.rank_strategies()


@router.get("/calibration")
async def get_confidence_calibration(strategy: str | None = None, db: AsyncSession = Depends(get_db)):
    service = StrategyRankingService(db)
    return await service.calibrate_confidence(strategy_name=strategy)
