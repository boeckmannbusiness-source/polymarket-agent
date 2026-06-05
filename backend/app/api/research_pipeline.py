from fastapi import APIRouter
from app.services.research.autonomous_research_pipeline import pipeline
from app.services.research.strategy_generator import strategy_generator
from app.services.incubator.strategy_incubator import incubator

router = APIRouter(prefix="/research", tags=["research_pipeline"])


@router.get("/reports")
async def get_reports():
    return {"reports": [r.model_dump() for r in await pipeline.get_reports()]}


@router.get("/candidates")
async def get_candidates():
    return {"candidates": [c.model_dump() for c in await pipeline.get_candidate_recommendations()]}


@router.get("/recommendations")
async def get_recommendations():
    return {"recommendations": [c.model_dump() for c in await pipeline.get_candidate_recommendations()]}


@router.post("/run")
async def run_pipeline():
    report = await pipeline.run()
    return {"report": report.model_dump()}


@router.get("/incubations")
async def get_incubations():
    return {"decisions": [d.model_dump() for d in await incubator.get_decisions()]}
