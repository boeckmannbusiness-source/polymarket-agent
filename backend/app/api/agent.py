from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.agent_service import AgentSnapshotService
from app.schemas.agent import (
    AgentPortfolioSnapshot,
    AgentStrategyPerformanceItem,
    AgentMarketState,
    AgentRiskState,
    AgentFullSnapshot,
)

router = APIRouter()


@router.get("/portfolio", response_model=AgentPortfolioSnapshot)
async def get_agent_portfolio(db: AsyncSession = Depends(get_db)):
    service = AgentSnapshotService(db)
    return await service.get_portfolio()


@router.get("/strategies", response_model=list[AgentStrategyPerformanceItem])
async def get_agent_strategies(db: AsyncSession = Depends(get_db)):
    service = AgentSnapshotService(db)
    return await service.get_strategies()


@router.get("/market-state", response_model=AgentMarketState)
async def get_agent_market_state(db: AsyncSession = Depends(get_db)):
    service = AgentSnapshotService(db)
    return await service.get_market_state()


@router.get("/risk", response_model=AgentRiskState)
async def get_agent_risk(db: AsyncSession = Depends(get_db)):
    service = AgentSnapshotService(db)
    return await service.get_risk_state()


@router.get("/snapshot", response_model=AgentFullSnapshot)
async def get_agent_snapshot(db: AsyncSession = Depends(get_db)):
    service = AgentSnapshotService(db)
    return await service.get_full_snapshot()
