from fastapi import APIRouter

from app.services.intelligence.portfolio_intelligence_service import portfolio_intelligence_service
from app.services.intelligence.resilience_service import resilience_service
from app.services.intelligence.stress_testing_service import stress_testing_service
from app.services.intelligence.investment_committee_service import investment_committee_service
from app.services.intelligence.autonomous_portfolio_review import autonomous_portfolio_review

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/portfolio")
async def get_portfolio_intelligence():
    latest = await portfolio_intelligence_service.get_latest()
    all_reports = await portfolio_intelligence_service.get_all()
    return {"latest": latest.model_dump() if latest else None, "history": [r.model_dump() for r in all_reports]}


@router.get("/resilience")
async def get_resilience():
    latest = await resilience_service.get_latest()
    all_reports = await resilience_service.get_all()
    return {"latest": latest.model_dump() if latest else None, "history": [r.model_dump() for r in all_reports]}


@router.get("/stress-tests")
async def get_stress_tests():
    scenarios = await stress_testing_service.get_scenarios()
    results = await stress_testing_service.get_latest_results()
    return {"scenarios": [s.model_dump() for s in scenarios], "results": [r.model_dump() for r in results]}


@router.get("/committee")
async def get_committee():
    latest = await investment_committee_service.get_latest()
    all_reports = await investment_committee_service.get_all()
    return {"latest": latest.model_dump() if latest else None, "history": [r.model_dump() for r in all_reports]}


@router.get("/reviews")
async def get_reviews():
    reviews = await autonomous_portfolio_review.get_reviews()
    return {"reviews": [r.model_dump() for r in reviews]}


@router.post("/review/run")
async def run_review():
    review = await autonomous_portfolio_review.run()
    return {"review": review.model_dump()}
