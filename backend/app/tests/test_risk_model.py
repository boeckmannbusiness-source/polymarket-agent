import pytest
from app.services.optimization.risk_model_service import RiskModelService


@pytest.fixture
def service():
    return RiskModelService()


@pytest.mark.asyncio
async def test_covariance_symmetry(service):
    sids = ["a", "b", "c"]
    base_corr = {
        "a": {"a": 1.0, "b": 0.3, "c": 0.1},
        "b": {"a": 0.3, "b": 1.0, "c": 0.2},
        "c": {"a": 0.1, "b": 0.2, "c": 1.0},
    }
    output = await service.compute(strategy_ids=sids, base_correlations=base_corr)
    cov = output.covariance_matrix
    for i in range(len(cov)):
        for j in range(len(cov)):
            assert abs(cov[i][j] - cov[j][i]) < 0.001


@pytest.mark.asyncio
async def test_correlation_spike_adjustment(service):
    sids = ["a", "b"]
    base_corr = {
        "a": {"a": 1.0, "b": 0.5},
        "b": {"a": 0.5, "b": 1.0},
    }
    normal = await service.compute(strategy_ids=sids, base_correlations=base_corr, correlation_spike_factor=1.0)
    spiked = await service.compute(strategy_ids=sids, base_correlations=base_corr, correlation_spike_factor=2.0)
    assert spiked.adjustment_factor > normal.adjustment_factor


@pytest.mark.asyncio
async def test_diagonal_positive(service):
    sids = ["a", "b"]
    output = await service.compute(strategy_ids=sids)
    for i in range(len(output.covariance_matrix)):
        assert output.covariance_matrix[i][i] > 0


@pytest.mark.asyncio
async def test_empty_input(service):
    output = await service.compute(strategy_ids=[])
    assert len(output.strategies) == 0
    assert len(output.covariance_matrix) == 0


@pytest.mark.asyncio
async def test_regime_adjustment_factor(service):
    sids = ["a"]
    output = await service.compute(strategy_ids=sids, regime="high_volatility")
    assert output.adjustment_factor > 1.0
    assert output.regime == "high_volatility"


@pytest.mark.asyncio
async def test_correlations_output(service):
    sids = ["a", "b"]
    base_corr = {
        "a": {"a": 1.0, "b": 0.5},
        "b": {"a": 0.5, "b": 1.0},
    }
    output = await service.compute(strategy_ids=sids, base_correlations=base_corr)
    assert "a" in output.correlations
    assert "b" in output.correlations


@pytest.mark.asyncio
async def test_correlation_bounds(service):
    sids = ["a", "b"]
    base_corr = {
        "a": {"a": 1.0, "b": 0.99},
        "b": {"a": 0.99, "b": 1.0},
    }
    output = await service.compute(strategy_ids=sids, base_correlations=base_corr)
    for si in sids:
        for sj in sids:
            c = output.correlations[si][sj]
            assert -1.0 <= c <= 1.0


@pytest.mark.asyncio
async def test_single_strategy(service):
    output = await service.compute(strategy_ids=["a"])
    assert len(output.strategies) == 1
    assert len(output.covariance_matrix) == 1


@pytest.mark.asyncio
async def test_generated_at_set(service):
    output = await service.compute(strategy_ids=["a"])
    assert output.generated_at != ""
