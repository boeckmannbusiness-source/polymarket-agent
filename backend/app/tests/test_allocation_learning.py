import pytest
from app.services.optimization.allocation_learning_service import AllocationLearningService


@pytest.fixture
def service():
    return AllocationLearningService()


@pytest.mark.asyncio
async def test_weight_adjustment_direction(service):
    curr = {"s1": 0.5, "s2": 0.5}
    er = {"s1": 0.10, "s2": 0.01}
    actual = {"s1": 0.15, "s2": 0.00}
    output = await service.update(current_weights=curr, expected_returns=er, actual_returns=actual, seed=42)
    s1_update = next(u for u in output.updates if u.strategy_id == "s1")
    s2_update = next(u for u in output.updates if u.strategy_id == "s2")
    assert s1_update.adjusted_weight >= s1_update.previous_weight or abs(s1_update.adjusted_weight - s1_update.previous_weight) < 0.01
    assert s2_update.adjusted_weight <= s2_update.previous_weight or abs(s2_update.adjusted_weight - s2_update.previous_weight) < 0.01


@pytest.mark.asyncio
async def test_clipping_to_caps(service):
    curr = {"s1": 0.5}
    er = {"s1": 0.10}
    actual = {"s1": 0.20}
    caps = {"s1": 10.0}
    output = await service.update(current_weights=curr, expected_returns=er, actual_returns=actual, tier_caps=caps, seed=42)
    s1_update = next(u for u in output.updates if u.strategy_id == "s1")
    assert s1_update.adjusted_weight <= 0.10


@pytest.mark.asyncio
async def test_stress_penalty_applied(service):
    curr = {"s1": 0.5}
    er = {"s1": 0.10}
    stress = {"s1": 20.0}
    output = await service.update(current_weights=curr, expected_returns=er, stress_survivability=stress, seed=42)
    s1_update = next(u for u in output.updates if u.strategy_id == "s1")
    assert s1_update.adjusted_weight < s1_update.previous_weight


@pytest.mark.asyncio
async def test_regime_calibration(service):
    regime_acc = {"trending": 0.8, "mean_reverting": 0.3}
    output = await service.update(current_weights={"s1": 1.0}, expected_returns={"s1": 0.05}, regime_accuracy=regime_acc, seed=42)
    assert "trending" in output.regime_calibration
    assert "mean_reverting" in output.regime_calibration
    for regime, cal in output.regime_calibration.items():
        assert 0.1 <= cal <= 1.0


@pytest.mark.asyncio
async def test_deterministic_with_seed(service):
    curr = {"s1": 0.5, "s2": 0.5}
    er = {"s1": 0.10, "s2": 0.02}
    actual = {"s1": 0.12, "s2": 0.01}
    o1 = await service.update(current_weights=curr, expected_returns=er, actual_returns=actual, seed=42)
    o2 = await service.update(current_weights=curr, expected_returns=er, actual_returns=actual, seed=42)
    for u1, u2 in zip(o1.updates, o2.updates):
        assert u1.adjusted_weight == u2.adjusted_weight


@pytest.mark.asyncio
async def test_no_negative_weights(service):
    curr = {"s1": 0.5}
    er = {"s1": -0.20}
    actual = {"s1": -0.50}
    output = await service.update(current_weights=curr, expected_returns=er, actual_returns=actual, seed=42)
    s1_update = next(u for u in output.updates if u.strategy_id == "s1")
    assert s1_update.adjusted_weight >= 0.0


@pytest.mark.asyncio
async def test_learning_signal_computed(service):
    curr = {"s1": 0.5}
    er = {"s1": 0.10}
    actual = {"s1": 0.15}
    output = await service.update(current_weights=curr, expected_returns=er, actual_returns=actual, seed=42)
    s1_update = next(u for u in output.updates if u.strategy_id == "s1")
    assert s1_update.learning_signal != 0.0


@pytest.mark.asyncio
async def test_risk_penalty_update(service):
    curr = {"s1": 0.5, "s2": 0.5}
    er = {"s1": 0.10, "s2": 0.05}
    stress = {"s1": 25.0}
    output = await service.update(current_weights=curr, expected_returns=er, stress_survivability=stress, seed=42)
    assert "s1" in output.risk_penalty_update
    assert output.risk_penalty_update["s1"] > 0.0
