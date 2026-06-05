import pytest
from app.services.intelligence.stress_testing_service import StressTestingService, SCENARIO_TYPES


@pytest.fixture
def service():
    svc = StressTestingService()
    svc._local_scenarios.clear()
    svc._local_results.clear()
    return svc


@pytest.mark.asyncio
async def test_run_scenario(service):
    scenario, result = await service.run_scenario("market_crash")
    assert scenario is not None
    assert result is not None
    assert scenario.scenario_type == "market_crash"
    assert result.scenario_type == "market_crash"
    assert 0 <= result.expected_drawdown <= 1
    assert result.resilience_score >= 0
    assert result.executed_at != ""


@pytest.mark.asyncio
async def test_run_all_scenarios(service):
    results = await service.run_all_scenarios()
    assert len(results) == len(SCENARIO_TYPES)
    types = {r.scenario_type for r in results}
    assert types == set(SCENARIO_TYPES.keys())


@pytest.mark.asyncio
async def test_stress_with_health_data(service):
    health = [
        {"strategy_id": "s1", "score": 80},
        {"strategy_id": "s2", "score": 50},
    ]
    _, result = await service.run_scenario("strategy_failure", strategy_health=health)
    assert "s1" in result.strategy_survivability
    assert "s2" in result.strategy_survivability


@pytest.mark.asyncio
async def test_deterministic_with_seed(service):
    _, r1 = await service.run_scenario("market_crash", seed=42)
    svc2 = StressTestingService()
    _, r2 = await svc2.run_scenario("market_crash", seed=42)
    assert r1.expected_drawdown == r2.expected_drawdown
    assert r1.resilience_score == r2.resilience_score


@pytest.mark.asyncio
async def test_get_scenarios(service):
    await service.run_scenario("market_crash")
    await service.run_scenario("news_shock")
    scenarios = await service.get_scenarios()
    assert len(scenarios) >= 2


@pytest.mark.asyncio
async def test_get_results(service):
    await service.run_scenario("market_crash")
    results = await service.get_results()
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_get_latest_results(service):
    await service.run_scenario("market_crash")
    await service.run_scenario("news_shock")
    await service.run_scenario("market_crash")
    latest = await service.get_latest_results()
    types = [r.scenario_type for r in latest]
    assert types.count("market_crash") == 1


@pytest.mark.asyncio
async def test_liquidity_collapse(service):
    _, result = await service.run_scenario("liquidity_collapse")
    assert result.expected_drawdown > 0


@pytest.mark.asyncio
async def test_correlation_spike(service):
    _, result = await service.run_scenario("correlation_spike")
    assert result.recovery_time_hours > 0
