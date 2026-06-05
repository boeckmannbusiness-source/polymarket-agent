import pytest
from app.services.intelligence.autonomous_portfolio_review import AutonomousPortfolioReview
from app.services.intelligence.portfolio_intelligence_service import portfolio_intelligence_service
from app.services.intelligence.resilience_service import resilience_service
from app.services.intelligence.stress_testing_service import stress_testing_service
from app.services.intelligence.investment_committee_service import investment_committee_service


@pytest.fixture
def service():
    svc = AutonomousPortfolioReview()
    svc._local_reviews.clear()
    return svc


@pytest.mark.asyncio
async def test_run_returns_review(service):
    review = await service.run()
    assert review is not None
    assert review.review_id != ""
    assert review.generated_at != ""
    assert review.summary != ""


@pytest.mark.asyncio
async def test_run_includes_intelligence(service):
    review = await service.run()
    assert review.intelligence is not None
    assert review.intelligence.quality_score >= 0


@pytest.mark.asyncio
async def test_run_includes_regime_plan(service):
    review = await service.run(regime_data={"regime": "trending", "confidence": 0.8})
    assert review.regime_allocation is not None
    assert review.regime_allocation.regime == "trending"


@pytest.mark.asyncio
async def test_run_includes_stress_tests(service):
    review = await service.run()
    assert len(review.stress_tests) >= 1


@pytest.mark.asyncio
async def test_run_includes_resilience(service):
    review = await service.run()
    assert review.resilience is not None
    assert review.resilience.survivability_score >= 0


@pytest.mark.asyncio
async def test_run_includes_committee(service):
    review = await service.run()
    assert review.committee is not None
    assert len(review.committee.recommendations) >= 1


@pytest.mark.asyncio
async def test_run_with_all_data(service):
    review = await service.run(
        market_data={"volatility": 0.3},
        tournament_rankings=[{"strategy_id": "s1", "rank": 1}],
        allocation_plans=[{"strategy_id": "s1", "allocation": 100}],
        strategy_health=[{"strategy_id": "s1", "score": 80}],
        strategy_performance=[{"strategy_id": "s1", "sharpe": 1.5}],
        candidate_recommendations=[{"candidate_id": "c1", "incubation_ready": True, "confidence": 0.6}],
        regime_data={"regime": "trending", "confidence": 0.8},
        strategy_correlations={"s1": {"s2": 0.5}},
        regime_exposure={"momentum": 100},
        tier_caps={"s1": 50},
        strategy_archetypes={"s1": "momentum_trend"},
        seed=42,
    )
    assert review.intelligence is not None
    assert review.regime_allocation is not None
    assert len(review.stress_tests) > 0
    assert review.resilience is not None
    assert review.committee is not None


@pytest.mark.asyncio
async def test_get_reviews(service):
    await service.run()
    reviews = await service.get_reviews()
    assert len(reviews) >= 1


@pytest.mark.asyncio
async def test_get_latest(service):
    await service.run()
    latest = await service.get_latest()
    assert latest is not None
    assert latest.review_id != ""


@pytest.mark.asyncio
async def test_run_deterministic(service):
    r1 = await service.run(seed=42)
    svc2 = AutonomousPortfolioReview()
    svc2._local_reviews.clear()
    r2 = await svc2.run(seed=42)
    assert r1.summary == r2.summary


@pytest.mark.asyncio
async def test_redis_fallback(service):
    review = await service.run()
    assert review is not None
    assert review.summary != ""
