from fastapi import APIRouter, Query

from app.services.shadow.shadow_analytics_service import analytics_service
from app.services.shadow.shadow_benchmark_service import benchmark_service
from app.services.shadow.shadow_promotion_service import promotion_service

router = APIRouter()


@router.get("/analytics")
async def get_all_analytics(
    start: str | None = Query(None, description="ISO start date filter"),
    end: str | None = Query(None, description="ISO end date filter"),
):
    results = await analytics_service.get_all_analytics(start=start, end=end)
    return {"analytics": [r.model_dump() for r in results]}


@router.get("/analytics/{strategy}")
async def get_strategy_analytics(
    strategy: str,
    start: str | None = Query(None, description="ISO start date filter"),
    end: str | None = Query(None, description="ISO end date filter"),
):
    result = await analytics_service.get_strategy_analytics(strategy, start=start, end=end)
    return result.model_dump()


@router.get("/benchmarks")
async def get_all_benchmarks():
    results = await benchmark_service.get_all_benchmarks()
    return {"benchmarks": [r.model_dump() for r in results]}


@router.get("/promotion")
async def get_all_promotions():
    results = await promotion_service.evaluate_all()
    return {"promotions": [r.model_dump() for r in results]}


@router.get("/promotion/{strategy}")
async def get_strategy_promotion(strategy: str):
    result = await promotion_service.evaluate_strategy(strategy)
    return result.model_dump()
