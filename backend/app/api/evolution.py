from fastapi import APIRouter, HTTPException
from app.services.evolution.population_service import population_service
from app.services.evolution.evolution_manager import manager
from app.services.evolution.mutation_engine import mutation_engine
from app.services.evolution.crossover_engine import crossover_engine
from app.services.research.strategy_candidate_service import candidate_service
from app.schemas.evolution import EvolutionRun

router = APIRouter(prefix="/evolution", tags=["evolution"])


@router.get("/population")
async def get_population():
    return {"population": [p.model_dump() for p in await population_service.get_population()]}


@router.get("/lineage")
async def get_lineage():
    return {"lineage": [l.model_dump() for l in await population_service.get_lineage()]}


@router.get("/candidates")
async def get_candidates():
    return {"candidates": [c.model_dump() for c in await population_service.get_candidates()]}


@router.get("/generations")
async def get_generations():
    return {"generations": await population_service.get_generations()}


@router.post("/run")
async def run_evolution():
    run = await manager.run_daily()
    return {"run": run.model_dump()}


@router.get("/runs")
async def get_runs():
    return {"runs": [r.model_dump() for r in await manager.get_runs()]}


@router.post("/candidates/{candidate_id}/promote")
async def promote_candidate(candidate_id: str):
    success = await manager.promote_candidate(candidate_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot promote candidate")
    return {"status": "promoted", "candidate_id": candidate_id}
