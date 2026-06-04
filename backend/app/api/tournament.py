from fastapi import APIRouter, Query

from app.services.shadow.strategy_tournament_service import tournament_service
from app.services.shadow.allocation_engine import allocation_engine
from app.services.shadow.portfolio_simulator import portfolio_simulator
from app.services.shadow.shadow_auto_promotion import auto_promotion_service

router = APIRouter()


@router.get("/rankings")
async def get_rankings():
    rankings = await tournament_service.get_rankings()
    return {"rankings": [r.model_dump() for r in rankings]}


@router.get("/allocations")
async def get_allocations(
    mode: str = Query("equal", description="Allocation mode: equal, sharpe, risk_parity, confidence, hybrid"),
    capital: float = Query(100000.0, description="Total capital to allocate"),
):
    result = await allocation_engine.compute_allocation(mode=mode, total_capital=capital)
    return result.model_dump()


@router.get("/allocations/all")
async def get_all_allocations(capital: float = Query(100000.0)):
    results = await allocation_engine.get_all_modes(total_capital=capital)
    return {"modes": [r.model_dump() for r in results]}


@router.get("/simulator")
async def get_simulation(
    capital: float = Query(100000.0, description="Starting capital"),
    mode: str = Query("equal", description="Allocation mode"),
):
    result = await portfolio_simulator.simulate(starting_capital=capital, mode=mode)
    return result.model_dump()


@router.get("/promotions")
async def get_promotion_recommendations():
    recommendations = await auto_promotion_service.get_recommendations()
    return {"recommendations": [r.model_dump() for r in recommendations]}
