import pytest
from app.services.intelligence.portfolio_intelligence_service import PortfolioIntelligenceService


@pytest.fixture
def service():
    svc = PortfolioIntelligenceService()
    svc._local_reports.clear()
    return svc


@pytest.mark.asyncio
async def test_compute_returns_report(service):
    report = await service.compute()
    assert report is not None
    assert 0 <= report.quality_score <= 100
    assert 0 <= report.diversification_score <= 100
    assert report.generated_at != ""


@pytest.mark.asyncio
async def test_compute_with_data(service):
    rankings = [{"strategy_id": "s1", "rank": 1}, {"strategy_id": "s2", "rank": 2}]
    plans = [{"strategy_id": "s1", "allocation": 60}, {"strategy_id": "s2", "allocation": 40}]
    health = [{"strategy_id": "s1", "score": 80}, {"strategy_id": "s2", "score": 60}]
    perf = [{"strategy_id": "s1", "sharpe": 1.5}, {"strategy_id": "s2", "sharpe": 0.5}]
    report = await service.compute(
        tournament_rankings=rankings,
        allocation_plans=plans,
        strategy_health=health,
        strategy_performance=perf,
        regime_data={"regime": "trending"},
    )
    assert report.quality_score > 0
    assert report.diversification_score > 0
    assert report.concentration_score > 0
    assert report.regime_fitness_score > 0


@pytest.mark.asyncio
async def test_quality_score_bounds(service):
    report = await service.compute()
    assert 0 <= report.quality_score <= 100
    assert 0 <= report.diversification_score <= 100
    assert 0 <= report.concentration_score <= 100
    assert 0 <= report.regime_fitness_score <= 100
    assert 0 <= report.strategy_overlap_score <= 100
    assert 0 <= report.capital_efficiency_score <= 100


@pytest.mark.asyncio
async def test_diversification_optimal(service):
    plans = [{"strategy_id": f"s{i}", "allocation": 100 / 5} for i in range(5)]
    report = await service.compute(allocation_plans=plans)
    assert report.diversification_score > 50


@pytest.mark.asyncio
async def test_concentration_single_strategy(service):
    plans = [{"strategy_id": "s1", "allocation": 100}]
    report = await service.compute(allocation_plans=plans)
    assert report.concentration_score > 50


@pytest.mark.asyncio
async def test_overlap_all_same(service):
    rankings = [{"strategy_id": "s1", "archetype": "momentum"}, {"strategy_id": "s2", "archetype": "momentum"}]
    report = await service.compute(tournament_rankings=rankings)
    assert report.strategy_overlap_score <= 51


@pytest.mark.asyncio
async def test_get_latest(service):
    await service.compute()
    latest = await service.get_latest()
    assert latest is not None
    assert latest.quality_score >= 0


@pytest.mark.asyncio
async def test_get_latest_empty(service):
    svc = PortfolioIntelligenceService()
    svc._local_reports.clear()
    latest = await svc.get_latest()
    assert latest is None


@pytest.mark.asyncio
async def test_get_all(service):
    await service.compute()
    await service.compute()
    all_reports = await service.get_all()
    assert len(all_reports) >= 2


@pytest.mark.asyncio
async def test_deterministic_scores(service):
    r1 = await service.compute(tournament_rankings=[{"strategy_id": "s1", "rank": 1}])
    svc2 = PortfolioIntelligenceService()
    svc2._local_reports.clear()
    r2 = await svc2.compute(tournament_rankings=[{"strategy_id": "s1", "rank": 1}])
    assert r1.quality_score == r2.quality_score
