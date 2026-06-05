import pytest
from app.services.optimization.regime_expected_return_model import RegimeExpectedReturnModel


@pytest.fixture
def model():
    return RegimeExpectedReturnModel()


@pytest.mark.asyncio
async def test_sum_p_times_mu_formula(model):
    probs = {"trending": 0.6, "mean_reverting": 0.4}
    perf = {
        "trending": {"strat_a": 0.10},
        "mean_reverting": {"strat_a": 0.05},
    }
    output = await model.compute(regime_probabilities=probs, strategy_performance_by_regime=perf)
    expected = 0.6 * 0.10 + 0.4 * 0.05
    assert len(output.returns) == 1
    assert abs(output.returns[0].expected_return - expected) < 0.001


@pytest.mark.asyncio
async def test_regime_weighting_correctness(model):
    probs = {"high_vol": 1.0, "low_vol": 0.0}
    perf = {
        "high_vol": {"s1": 0.08},
        "low_vol": {"s1": 0.02},
    }
    output = await model.compute(regime_probabilities=probs, strategy_performance_by_regime=perf)
    assert abs(output.returns[0].expected_return - 0.08) < 0.001


@pytest.mark.asyncio
async def test_confidence_scaling(model):
    probs = {"trending": 1.0}
    perf = {"trending": {"s1": 0.05}}
    conf = {"trending": 0.5}
    output = await model.compute(regime_probabilities=probs, strategy_performance_by_regime=perf, confidence_weights=conf)
    assert output.returns[0].confidence <= 1.0
    assert output.returns[0].confidence > 0.0


@pytest.mark.asyncio
async def test_multiple_strategies(model):
    probs = {"trending": 1.0}
    perf = {"trending": {"s1": 0.10, "s2": 0.05, "s3": 0.02}}
    output = await model.compute(regime_probabilities=probs, strategy_performance_by_regime=perf)
    assert len(output.returns) == 3


@pytest.mark.asyncio
async def test_empty_regime_probabilities(model):
    output = await model.compute(regime_probabilities={}, strategy_performance_by_regime={})
    assert len(output.returns) == 0


@pytest.mark.asyncio
async def test_regime_contributions_populated(model):
    probs = {"trending": 0.5, "mean_reverting": 0.5}
    perf = {
        "trending": {"s1": 0.10},
        "mean_reverting": {"s1": 0.04},
    }
    output = await model.compute(regime_probabilities=probs, strategy_performance_by_regime=perf)
    assert len(output.returns[0].regime_contributions) == 2
    assert "trending" in output.returns[0].regime_contributions
    assert "mean_reverting" in output.returns[0].regime_contributions


@pytest.mark.asyncio
async def test_zero_confidence_does_not_break(model):
    probs = {"trending": 1.0}
    perf = {"trending": {"s1": 0.05}}
    conf = {"trending": 0.0}
    output = await model.compute(regime_probabilities=probs, strategy_performance_by_regime=perf, confidence_weights=conf)
    assert len(output.returns) == 1


@pytest.mark.asyncio
async def test_regime_probabilities_in_output(model):
    probs = {"trending": 0.7, "mean_reverting": 0.3}
    output = await model.compute(regime_probabilities=probs, strategy_performance_by_regime={})
    assert output.regime_probabilities == probs
