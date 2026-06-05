import pytest
from app.services.optimization.monte_carlo_simulation_service import MonteCarloSimulationService


@pytest.fixture
def service():
    return MonteCarloSimulationService()


@pytest.mark.asyncio
async def test_1000_paths_generated(service):
    sids = ["a", "b"]
    weights = [0.5, 0.5]
    er = {"a": 0.05, "b": 0.03}
    report = await service.simulate(strategy_ids=sids, weights=weights, expected_returns=er, seed=42, n_paths=1000)
    assert report.n_paths == 1000


@pytest.mark.asyncio
async def test_percentile_count(service):
    sids = ["a"]
    weights = [1.0]
    er = {"a": 0.05}
    report = await service.simulate(strategy_ids=sids, weights=weights, expected_returns=er, seed=42, n_paths=100)
    assert len(report.percentile_paths) == 5
    labels = {p.percentile for p in report.percentile_paths}
    assert labels == {"p5", "p25", "p50", "p75", "p95"}


@pytest.mark.asyncio
async def test_expected_drawdown_non_negative(service):
    sids = ["a"]
    weights = [1.0]
    er = {"a": 0.05}
    report = await service.simulate(strategy_ids=sids, weights=weights, expected_returns=er, seed=42, n_paths=100)
    assert report.expected_drawdown >= 0.0


@pytest.mark.asyncio
async def test_survival_probability_bounds(service):
    sids = ["a"]
    weights = [1.0]
    er = {"a": 0.05}
    report = await service.simulate(strategy_ids=sids, weights=weights, expected_returns=er, seed=42, n_paths=100)
    assert 0.0 <= report.survival_probability <= 1.0


@pytest.mark.asyncio
async def test_deterministic_with_seed(service):
    sids = ["a", "b"]
    weights = [0.5, 0.5]
    er = {"a": 0.05, "b": 0.03}
    r1 = await service.simulate(strategy_ids=sids, weights=weights, expected_returns=er, seed=42, n_paths=50)
    r2 = await service.simulate(strategy_ids=sids, weights=weights, expected_returns=er, seed=42, n_paths=50)
    assert r1.expected_drawdown == r2.expected_drawdown
    assert r1.survival_probability == r2.survival_probability


@pytest.mark.asyncio
async def test_sharpe_mean_computed(service):
    sids = ["a"]
    weights = [1.0]
    er = {"a": 0.05}
    report = await service.simulate(strategy_ids=sids, weights=weights, expected_returns=er, seed=42, n_paths=50)
    assert report.sharpe_mean != 0.0


@pytest.mark.asyncio
async def test_empty_strategies(service):
    report = await service.simulate(strategy_ids=[], weights=[], seed=42)
    assert report.n_paths == 0
    assert report.n_steps == 0


@pytest.mark.asyncio
async def test_percentile_curves_have_correct_length(service):
    sids = ["a"]
    weights = [1.0]
    n_steps = 252
    report = await service.simulate(strategy_ids=sids, weights=weights, expected_returns={"a": 0.05}, seed=42, n_steps=n_steps, n_paths=50)
    for p in report.percentile_paths:
        assert len(p.equity_curve) == n_steps + 1
        assert len(p.drawdown_curve) == n_steps + 1


@pytest.mark.asyncio
async def test_worst_drawdown_ge_expected(service):
    sids = ["a"]
    weights = [1.0]
    report = await service.simulate(strategy_ids=sids, weights=weights, expected_returns={"a": 0.05}, seed=42, n_paths=100)
    assert report.worst_drawdown >= report.expected_drawdown
