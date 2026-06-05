import pytest
from app.services.optimization.autonomous_optimization_pipeline import AutonomousOptimizationPipeline


@pytest.fixture
def pipeline():
    return AutonomousOptimizationPipeline()


@pytest.mark.asyncio
async def test_report_structure(pipeline):
    sids = ["s1", "s2"]
    er = {"s1": 0.05, "s2": 0.03}
    report = await pipeline.run(
        strategy_ids=sids,
        expected_returns_map=er,
        regime="low_volatility",
        seed=42,
    )
    assert report.report_id.startswith("opt-")
    assert report.allocation is not None
    assert report.expected_returns is not None
    assert report.monte_carlo is not None
    assert report.learning is not None


@pytest.mark.asyncio
async def test_all_sub_services_populated(pipeline):
    sids = ["s1", "s2"]
    er = {"s1": 0.05, "s2": 0.03}
    perf_by_regime = {"low_volatility": {"s1": 0.05, "s2": 0.03}}
    report = await pipeline.run(
        strategy_ids=sids,
        expected_returns_map=er,
        strategy_performance_by_regime=perf_by_regime,
        regime="low_volatility",
        seed=42,
    )
    assert len(report.allocation.allocations) > 0
    assert len(report.expected_returns.returns) > 0
    assert report.monte_carlo.n_paths > 0
    assert len(report.learning.updates) > 0


@pytest.mark.asyncio
async def test_deterministic_with_seed(pipeline):
    sids = ["s1", "s2"]
    er = {"s1": 0.05, "s2": 0.03}
    r1 = await pipeline.run(strategy_ids=sids, expected_returns_map=er, seed=42)
    r2 = await pipeline.run(strategy_ids=sids, expected_returns_map=er, seed=42)
    assert r1.allocation.diagnostics.objective_value == r2.allocation.diagnostics.objective_value
    assert r1.monte_carlo.expected_drawdown == r2.monte_carlo.expected_drawdown


@pytest.mark.asyncio
async def test_empty_strategies(pipeline):
    report = await pipeline.run(strategy_ids=[], seed=42)
    assert report.report_id.startswith("opt-")
    assert report.summary != ""


@pytest.mark.asyncio
async def test_tier_caps_propagated(pipeline):
    sids = ["s1", "s2"]
    er = {"s1": 0.20, "s2": 0.01}
    caps = {"s1": 10.0, "s2": 100.0}
    report = await pipeline.run(
        strategy_ids=sids,
        expected_returns_map=er,
        tier_caps=caps,
        seed=42,
    )
    s1_alloc = next(a for a in report.allocation.allocations if a.strategy_id == "s1")
    assert s1_alloc.weight_pct <= 11.0


@pytest.mark.asyncio
async def test_regime_probabilities_used(pipeline):
    sids = ["s1"]
    er = {"s1": 0.05}
    regime_probs = {"trending": 0.7, "mean_reverting": 0.3}
    report = await pipeline.run(
        strategy_ids=sids,
        expected_returns_map=er,
        regime_probabilities=regime_probs,
        seed=42,
    )
    assert report.expected_returns is not None
    assert len(report.expected_returns.regime_probabilities) > 0


@pytest.mark.asyncio
async def test_summary_contains_key_metrics(pipeline):
    sids = ["s1", "s2"]
    er = {"s1": 0.05, "s2": 0.03}
    report = await pipeline.run(strategy_ids=sids, expected_returns_map=er, seed=42)
    assert "Optimized" in report.summary
    assert "drawdown" in report.summary


@pytest.mark.asyncio
async def test_stress_survivability_affects_learning(pipeline):
    sids = ["s1", "s2"]
    er = {"s1": 0.05, "s2": 0.03}
    curr_w = {"s1": 0.5, "s2": 0.5}
    stress = {"s1": 20.0}
    report = await pipeline.run(
        strategy_ids=sids,
        expected_returns_map=er,
        current_weights=curr_w,
        stress_survivability=stress,
        seed=42,
    )
    s1_learn = next(u for u in report.learning.updates if u.strategy_id == "s1")
    assert "low stress" in s1_learn.adjustment_reason


@pytest.mark.asyncio
async def test_current_weights_respected(pipeline):
    sids = ["s1", "s2"]
    er = {"s1": 0.05, "s2": 0.03}
    curr_w = {"s1": 0.8, "s2": 0.2}
    report = await pipeline.run(
        strategy_ids=sids,
        expected_returns_map=er,
        current_weights=curr_w,
        seed=42,
    )
    for u in report.learning.updates:
        assert u.previous_weight > 0
