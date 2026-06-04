from fastapi import APIRouter, Query

from app.services.research.strategy_registry import registry
from app.services.research.champion_challenger_service import champion_service
from app.services.research.strategy_health_service import health_service
from app.services.research.research_report_service import report_service

router = APIRouter()


@router.get("/registry")
async def get_registry(status: str | None = None):
    if status:
        strategies = await registry.get_active(status=status)
    else:
        strategies = await registry.get_all()
    return {"strategies": [s.model_dump() for s in strategies]}


@router.get("/registry/{strategy_id}")
async def get_registry_entry(strategy_id: str):
    meta = await registry.get(strategy_id)
    if not meta:
        return {"strategy": None}
    return {"strategy": meta.model_dump()}


@router.get("/registry/{strategy_id}/history")
async def get_strategy_history(strategy_id: str):
    history = await registry.get_history(strategy_id)
    return {"history": [h.model_dump() for h in history]}


@router.post("/registry/{strategy_id}/promote")
async def promote_strategy(strategy_id: str, target_status: str = Query(...), notes: str = Query("")):
    meta = await registry.promote(strategy_id, target_status, notes)
    if not meta:
        return {"status": "error", "message": "Strategy not found"}
    return {"status": "ok", "strategy": meta.model_dump()}


@router.post("/registry/{strategy_id}/retire")
async def retire_strategy(strategy_id: str, successor: str | None = Query(None), notes: str = Query("")):
    meta = await registry.retire(strategy_id, successor, notes)
    if not meta:
        return {"status": "error", "message": "Strategy not found"}
    return {"status": "ok", "strategy": meta.model_dump()}


@router.get("/champion")
async def get_champion():
    result = await champion_service.evaluate()
    return result.model_dump()


@router.get("/health")
async def get_all_health():
    results = await health_service.get_all_health()
    return {"health": [h.model_dump() for h in results]}


@router.get("/health/{strategy}")
async def get_strategy_health(strategy: str):
    h = await health_service.compute_health(strategy)
    return h.model_dump()


@router.post("/health/invalidate")
async def invalidate_health_cache():
    await health_service.invalidate_cache()
    return {"status": "ok"}


@router.get("/report/{strategy}")
async def get_strategy_report(strategy: str):
    report = await report_service.generate_strategy_report(strategy)
    return report.model_dump()


@router.get("/report/portfolio")
async def get_portfolio_report():
    report = await report_service.generate_portfolio_report()
    return report.model_dump()


@router.post("/report/invalidate")
async def invalidate_report_cache():
    await report_service.invalidate_cache()
    return {"status": "ok"}
