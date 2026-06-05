import pytest
from app.services.intelligence.resilience_service import ResilienceService


@pytest.fixture
def service():
    svc = ResilienceService()
    svc._local_reports.clear()
    return svc


@pytest.mark.asyncio
async def test_compute_returns_report(service):
    report = await service.compute()
    assert report is not None
    assert 0 <= report.concentration_risk <= 100
    assert 0 <= report.dependency_risk <= 100
    assert report.generated_at != ""


@pytest.mark.asyncio
async def test_concentration_risk_high_when_single(service):
    allocs = [{"strategy_id": "s1", "allocation": 100}]
    report = await service.compute(allocations=allocs)
    assert report.concentration_risk > 50


@pytest.mark.asyncio
async def test_concentration_risk_low_when_diversified(service):
    allocs = [{"strategy_id": f"s{i}", "allocation": 100 / 10} for i in range(10)]
    report = await service.compute(allocations=allocs)
    assert report.concentration_risk < 30


@pytest.mark.asyncio
async def test_dependency_risk(service):
    corrs = {"s1": {"s2": 0.8, "s3": 0.6}, "s2": {"s1": 0.8}, "s3": {"s1": 0.6}}
    report = await service.compute(strategy_correlations=corrs)
    assert report.dependency_risk > 0


@pytest.mark.asyncio
async def test_dependency_risk_zero_when_empty(service):
    report = await service.compute(strategy_correlations={})
    assert report.dependency_risk == 0


@pytest.mark.asyncio
async def test_single_strategy_exposure(service):
    allocs = [{"strategy_id": "s1", "allocation": 50}, {"strategy_id": "s2", "allocation": 30}]
    report = await service.compute(allocations=allocs)
    assert report.single_strategy_exposure == 50


@pytest.mark.asyncio
async def test_single_regime_exposure(service):
    regime_exp = {"momentum": 60, "arbitrage": 40}
    report = await service.compute(regime_exposure=regime_exp)
    assert report.single_regime_exposure == 60


@pytest.mark.asyncio
async def test_survivability(service):
    health = [{"strategy_id": "s1", "score": 80}, {"strategy_id": "s2", "score": 60}]
    report = await service.compute(strategy_health=health)
    assert report.survivability_score > 0


@pytest.mark.asyncio
async def test_get_latest(service):
    await service.compute()
    latest = await service.get_latest()
    assert latest is not None


@pytest.mark.asyncio
async def test_get_all(service):
    await service.compute()
    await service.compute()
    reports = await service.get_all()
    assert len(reports) >= 2
