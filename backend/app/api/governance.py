from fastapi import APIRouter
from app.services.lifecycle.strategy_lifecycle_manager import lifecycle_manager
from app.services.allocation.capital_allocator import capital_allocator
from app.services.allocation.autonomous_portfolio_manager import portfolio_manager
from app.services.governance.strategy_governance import governance
from app.schemas.lifecycle import TierLimits
from datetime import datetime, timezone

router = APIRouter()


@router.get("/governance/decisions")
async def get_governance_decisions():
    return {"decisions": [d.model_dump() for d in await lifecycle_manager.get_decisions()]}


@router.get("/governance/promotions")
async def get_governance_promotions():
    return {"promotions": [p.model_dump() for p in await lifecycle_manager.get_promotions()]}


@router.get("/governance/retirements")
async def get_governance_retirements():
    return {"retirements": [r.model_dump() for r in await lifecycle_manager.get_retirements()]}


@router.get("/governance/allocations")
async def get_governance_allocations():
    return {"allocations": [a.model_dump() for a in await capital_allocator.get_plans()]}


@router.get("/governance/records")
async def get_governance_records():
    return {"records": [r.model_dump() for r in await governance.get_records()]}


@router.post("/governance/explain")
async def explain_governance(record_type: str = "all"):
    records = await governance.get_records()
    return {"records": [r.model_dump() for r in records]}


@router.get("/portfolio-manager/recommendation")
async def get_portfolio_recommendation():
    rec = await portfolio_manager.get_latest_recommendation()
    if not rec:
        return {"recommendation": None}
    return {"recommendation": rec.model_dump()}


@router.get("/portfolio-manager/allocation-plan")
async def get_allocation_plan():
    plans = await capital_allocator.get_plans()
    if not plans:
        return {"plan": None}
    return {"plan": plans[-1].model_dump()}


@router.post("/portfolio-manager/run")
async def run_portfolio_manager():
    strategies = _get_mock_strategies()
    rec = await portfolio_manager.run_review(strategies)
    return {"recommendation": rec.model_dump()}


def _get_mock_strategies() -> list[dict]:
    return [
        {"strategy_id": "strat-alpha", "tier": "LIVE", "total_trades": 245, "sharpe": 2.1, "drawdown": 0.048, "confidence": 0.88, "health_score": 92, "rank": 1, "alpha": 0.25, "circuit_breaker_count": 0},
        {"strategy_id": "strat-beta", "tier": "LIVE", "total_trades": 182, "sharpe": 1.5, "drawdown": 0.072, "confidence": 0.81, "health_score": 85, "rank": 2, "alpha": 0.18, "circuit_breaker_count": 0},
        {"strategy_id": "strat-gamma", "tier": "PAPER", "total_trades": 89, "sharpe": 1.1, "drawdown": 0.095, "confidence": 0.74, "health_score": 72, "rank": 3, "alpha": 0.12, "circuit_breaker_count": 0},
        {"strategy_id": "strat-delta", "tier": "PAPER", "total_trades": 54, "sharpe": 0.8, "drawdown": 0.12, "confidence": 0.65, "health_score": 68, "rank": 4, "alpha": 0.05, "circuit_breaker_count": 0},
        {"strategy_id": "strat-epsilon", "tier": "SHADOW", "total_trades": 132, "sharpe": 2.1, "drawdown": 0.055, "confidence": 0.82, "health_score": 78, "rank": 5, "alpha": 0.22, "circuit_breaker_count": 0},
        {"strategy_id": "strat-zeta", "tier": "SHADOW", "total_trades": 12, "sharpe": -0.3, "drawdown": 0.35, "confidence": 0.25, "health_score": 22, "rank": 6, "alpha": -0.15, "circuit_breaker_count": 3},
    ]
