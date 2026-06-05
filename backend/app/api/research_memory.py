from fastapi import APIRouter
from app.services.research.research_memory import research_memory
from app.services.research.market_regime_service import market_regime_service

router = APIRouter(prefix="/research", tags=["research_memory"])


@router.get("/memory")
async def get_research_memory(entry_type: str | None = None):
    return {"entries": [e.model_dump() for e in await research_memory.get_memory(entry_type=entry_type)]}


@router.get("/hypotheses")
async def get_hypotheses(status: str | None = None):
    if status:
        return {"hypotheses": [h.model_dump() for h in await research_memory.get_hypotheses() if h.status == status]}
    return {"hypotheses": [h.model_dump() for h in await research_memory.get_hypotheses()]}


@router.get("/regimes")
async def get_regimes():
    return {"regimes": [r.model_dump() for r in await research_memory.get_regimes()]}


@router.get("/regimes/current")
async def get_current_regime():
    regime = await market_regime_service.get_current_regime()
    return {"regime": regime.model_dump() if regime else None}
