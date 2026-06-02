from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.portfolio import (
    PortfolioSnapshot,
    PositionView,
    StrategyPerformance,
    TradeTimeline,
    MarketExposure,
)
from app.services.portfolio.portfolio_snapshot_service import PortfolioSnapshotService
from app.services.portfolio.strategy_performance_service import StrategyPerformanceService
from app.services.portfolio.execution_timeline_service import ExecutionTimelineService
from app.services.portfolio.position_view_service import PositionViewService
from app.services.portfolio.exposure_service import ExposureService
from app.services.portfolio.portfolio_cache_service import PortfolioCacheService

router = APIRouter()
cache_service = PortfolioCacheService()


@router.get("/summary", response_model=PortfolioSnapshot)
async def get_portfolio_summary(db: AsyncSession = Depends(get_db)):
    cached = await cache_service.get("snapshot:overview")
    if cached is not None:
        return PortfolioSnapshot(**cached)

    service = PortfolioSnapshotService(db)
    snapshot = await service.get_portfolio_snapshot()

    await cache_service.set("snapshot:overview", snapshot.model_dump(), ttl_seconds=15)
    return snapshot


@router.get("/positions", response_model=list[PositionView])
async def get_positions(
    status: str | None = Query(default=None, pattern="^(OPEN|CLOSED)?$"),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"position_view:all"
    if status:
        cache_key = f"position_view:{status}"

    cached = await cache_service.get(cache_key)
    if cached is not None:
        return [PositionView(**p) for p in cached]

    service = PositionViewService(db)
    all_positions = await service.get_positions_overview()

    if status == "OPEN":
        all_positions = [p for p in all_positions if p.size > 0]
    elif status == "CLOSED":
        all_positions = [p for p in all_positions if p.size == 0]

    await cache_service.set(cache_key, [p.model_dump() for p in all_positions], ttl_seconds=10)
    return all_positions


@router.get("/strategies", response_model=list[StrategyPerformance])
async def get_all_strategies(db: AsyncSession = Depends(get_db)):
    from app.models import Trade
    from sqlalchemy import select, func

    service = StrategyPerformanceService(db)
    result = await db.execute(
        select(Trade.agent_id, func.count(Trade.id).label("cnt"))
        .where(Trade.agent_id.isnot(None))
        .group_by(Trade.agent_id)
        .order_by(func.count(Trade.id).desc())
    )
    agent_rows = result.all()

    strategies = []
    for row in agent_rows:
        cached = await cache_service.get(f"strategy_kpis:{row.agent_id}")
        if cached is not None:
            strategies.append(StrategyPerformance(**cached))
        else:
            perf = await service.get_strategy_summary(row.agent_id)
            await cache_service.set(f"strategy_kpis:{row.agent_id}", perf.model_dump(), ttl_seconds=60)
            strategies.append(perf)

    return strategies


@router.get("/strategies/{agent_id}", response_model=StrategyPerformance)
async def get_strategy_detail(agent_id: str, db: AsyncSession = Depends(get_db)):
    cached = await cache_service.get(f"strategy_kpis:{agent_id}")
    if cached is not None:
        return StrategyPerformance(**cached)

    service = StrategyPerformanceService(db)
    perf = await service.get_strategy_summary(agent_id)
    await cache_service.set(f"strategy_kpis:{agent_id}", perf.model_dump(), ttl_seconds=60)
    return perf


@router.get("/strategies/{agent_id}/pnl-curve")
async def get_strategy_pnl_curve(agent_id: str, db: AsyncSession = Depends(get_db)):
    cached = await cache_service.get(f"strategy_pnl_curve:{agent_id}")
    if cached is not None:
        return cached

    service = StrategyPerformanceService(db)
    curve = await service.get_strategy_pnl_curve(agent_id)
    data = [p.model_dump() for p in curve]
    await cache_service.set(f"strategy_pnl_curve:{agent_id}", data, ttl_seconds=60)
    return data


@router.get("/trades/{trade_id}/timeline", response_model=TradeTimeline)
async def get_trade_timeline(trade_id: UUID, db: AsyncSession = Depends(get_db)):
    cached = await cache_service.get(f"trade_timeline:{trade_id}")
    if cached is not None:
        return TradeTimeline(**cached)

    service = ExecutionTimelineService(db)
    timeline = await service.get_trade_timeline(trade_id)
    await cache_service.set(f"trade_timeline:{trade_id}", timeline.model_dump(), ttl_seconds=30)
    return timeline


@router.get("/exposure", response_model=MarketExposure)
async def get_market_exposure(db: AsyncSession = Depends(get_db)):
    cached = await cache_service.get("market_exposure:overview")
    if cached is not None:
        return MarketExposure(**cached)

    service = ExposureService(db)
    exposure = await service.get_market_exposure()
    await cache_service.set("market_exposure:overview", exposure.model_dump(), ttl_seconds=15)
    return exposure
