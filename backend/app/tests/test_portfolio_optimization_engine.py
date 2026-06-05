import pytest
from app.services.optimization.portfolio_optimization_engine import PortfolioOptimizationEngine


@pytest.fixture
def engine():
    return PortfolioOptimizationEngine()


@pytest.mark.asyncio
async def test_weights_sum_to_one(engine):
    sids = ["strat_a", "strat_b", "strat_c"]
    er = {"strat_a": 0.05, "strat_b": 0.03, "strat_c": 0.02}
    output = await engine.optimize_portfolio(strategy_ids=sids, expected_returns=er, seed=42)
    total = sum(a.weight_pct for a in output.allocations)
    assert abs(total - 100.0) < 1.0


@pytest.mark.asyncio
async def test_constraints_enforced(engine):
    sids = ["strat_a", "strat_b"]
    er = {"strat_a": 0.10, "strat_b": 0.01}
    caps = {"strat_a": 30.0, "strat_b": 100.0}
    output = await engine.optimize_portfolio(strategy_ids=sids, expected_returns=er, tier_caps=caps, seed=42)
    for a in output.allocations:
        cap = caps.get(a.strategy_id, 100.0)
        assert a.weight_pct <= cap + 1.0


@pytest.mark.asyncio
async def test_deterministic_with_seed(engine):
    sids = ["strat_a", "strat_b", "strat_c"]
    er = {"strat_a": 0.05, "strat_b": 0.03, "strat_c": 0.02}
    out1 = await engine.optimize_portfolio(strategy_ids=sids, expected_returns=er, seed=42)
    engine._local_outputs.clear()
    out2 = await engine.optimize_portfolio(strategy_ids=sids, expected_returns=er, seed=42)
    for a1, a2 in zip(out1.allocations, out2.allocations):
        assert a1.weight_pct == a2.weight_pct


@pytest.mark.asyncio
async def test_tier_caps_respected(engine):
    sids = ["strat_a", "strat_b"]
    er = {"strat_a": 0.20, "strat_b": 0.01}
    caps = {"strat_a": 10.0, "strat_b": 100.0}
    output = await engine.optimize_portfolio(strategy_ids=sids, expected_returns=er, tier_caps=caps, seed=42)
    strat_a = next(a for a in output.allocations if a.strategy_id == "strat_a")
    assert strat_a.weight_pct <= 11.0


@pytest.mark.asyncio
async def test_empty_strategies(engine):
    output = await engine.optimize_portfolio(strategy_ids=[], expected_returns={}, seed=42)
    assert len(output.allocations) == 0


@pytest.mark.asyncio
async def test_single_strategy(engine):
    sids = ["strat_a"]
    er = {"strat_a": 0.05}
    output = await engine.optimize_portfolio(strategy_ids=sids, expected_returns=er, seed=42)
    assert len(output.allocations) == 1
    assert abs(output.allocations[0].weight_pct - 100.0) < 1.0


@pytest.mark.asyncio
async def test_diagnostics_present(engine):
    sids = ["strat_a", "strat_b"]
    er = {"strat_a": 0.05, "strat_b": 0.03}
    output = await engine.optimize_portfolio(strategy_ids=sids, expected_returns=er, seed=42)
    assert output.diagnostics is not None
    assert output.diagnostics.objective_value != 0.0


@pytest.mark.asyncio
async def test_risk_contributions_computed(engine):
    sids = ["strat_a", "strat_b"]
    er = {"strat_a": 0.05, "strat_b": 0.03}
    cov = {
        "strat_a": {"strat_a": 0.04, "strat_b": 0.01},
        "strat_b": {"strat_a": 0.01, "strat_b": 0.02},
    }
    output = await engine.optimize_portfolio(strategy_ids=sids, expected_returns=er, covariance=cov, seed=42)
    for a in output.allocations:
        assert a.risk_contribution >= 0.0


@pytest.mark.asyncio
async def test_no_negative_weights(engine):
    sids = ["strat_a", "strat_b"]
    er = {"strat_a": -0.05, "strat_b": -0.03}
    output = await engine.optimize_portfolio(strategy_ids=sids, expected_returns=er, seed=42)
    for a in output.allocations:
        assert a.weight_pct >= 0.0
