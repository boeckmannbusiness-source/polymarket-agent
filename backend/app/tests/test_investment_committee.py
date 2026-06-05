import pytest
from app.schemas.intelligence import PortfolioIntelligenceReport, ResilienceReport, StressTestResult
from app.services.intelligence.investment_committee_service import InvestmentCommitteeService


@pytest.fixture
def service():
    svc = InvestmentCommitteeService()
    svc._local_reports.clear()
    return svc


@pytest.mark.asyncio
async def test_generates_report(service):
    report = await service.generate()
    assert report is not None
    assert report.report_id != ""
    assert report.generated_at != ""
    assert len(report.recommendations) >= 1


@pytest.mark.asyncio
async def test_recommends_when_quality_low(service):
    intel = PortfolioIntelligenceReport(quality_score=30)
    report = await service.generate(intelligence=intel)
    recos = [r for r in report.recommendations if r.recommendation_type == "reduce_concentration"]
    assert len(recos) >= 1


@pytest.mark.asyncio
async def test_recommends_when_concentration_high(service):
    intel = PortfolioIntelligenceReport(concentration_score=70)
    report = await service.generate(intelligence=intel)
    recos = [r for r in report.recommendations if r.recommendation_type == "reduce_concentration"]
    assert len(recos) >= 1


@pytest.mark.asyncio
async def test_recommends_retirement_for_low_sharpe(service):
    intel = PortfolioIntelligenceReport(quality_score=60, diversification_score=50, concentration_score=30)
    perf = [{"strategy_id": "bad1", "sharpe": -1.0}, {"strategy_id": "good1", "sharpe": 2.0}]
    report = await service.generate(intelligence=intel, strategy_performance=perf)
    recos = [r for r in report.recommendations if r.recommendation_type == "retire_strategy"]
    assert len(recos) >= 1


@pytest.mark.asyncio
async def test_recommends_increase_for_high_sharpe(service):
    intel = PortfolioIntelligenceReport(quality_score=60, diversification_score=50, concentration_score=30)
    perf = [{"strategy_id": "good1", "sharpe": 2.0}]
    report = await service.generate(intelligence=intel, strategy_performance=perf)
    recos = [r for r in report.recommendations if r.recommendation_type == "increase_allocation"]
    assert len(recos) >= 1


@pytest.mark.asyncio
async def test_stress_recommendations(service):
    results = [StressTestResult(
        scenario_id="st1", scenario_type="market_crash",
        expected_drawdown=0.5, recovery_time_hours=100, resilience_score=20,
        strategy_survivability={"s1": 25, "s2": 60},
    )]
    report = await service.generate(stress_results=results)
    assert len(report.recommendations) >= 1


@pytest.mark.asyncio
async def test_resilience_recommendations(service):
    res = ResilienceReport(concentration_risk=70, dependency_risk=50, single_strategy_exposure=40, single_regime_exposure=30, survivability_score=35)
    report = await service.generate(resilience=res)
    assert len(report.recommendations) >= 3


@pytest.mark.asyncio
async def test_candidate_recommendations(service):
    candidates = [{"candidate_id": "c1", "incubation_ready": True, "confidence": 0.6, "novelty_score": 0.5}]
    report = await service.generate(candidate_recommendations=candidates)
    recos = [r for r in report.recommendations if r.recommendation_type == "incubate_candidate"]
    assert len(recos) >= 1


@pytest.mark.asyncio
async def test_get_latest(service):
    await service.generate()
    latest = await service.get_latest()
    assert latest is not None
    assert latest.report_id != ""


@pytest.mark.asyncio
async def test_get_all(service):
    await service.generate()
    await service.generate()
    reports = await service.get_all()
    assert len(reports) >= 2
