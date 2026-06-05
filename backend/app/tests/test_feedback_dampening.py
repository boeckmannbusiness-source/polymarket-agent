import pytest
from app.services.control.feedback_dampening_service import FeedbackDampeningService


@pytest.mark.asyncio
async def test_dampening_factor_between_01_and_10():
    fds = FeedbackDampeningService()
    report = await fds.dampen(
        learning_signals={"a": 0.5, "b": -0.3},
        volatility_estimate=0.5,
        regime_instability=0.3,
        allocation_variance=0.2,
    )
    assert 0.1 <= report.global_stability_factor <= 1.0


@pytest.mark.asyncio
async def test_no_penalty_with_zero_inputs():
    fds = FeedbackDampeningService()
    report = await fds.dampen(
        learning_signals={"a": 0.5},
        volatility_estimate=0.0,
        regime_instability=0.0,
        allocation_variance=0.0,
    )
    assert report.global_stability_factor == 1.0


@pytest.mark.asyncio
async def test_high_volatility_reduces_stability():
    fds = FeedbackDampeningService()
    r_low = await fds.dampen(learning_signals={"a": 0.5}, volatility_estimate=0.1)
    r_high = await fds.dampen(learning_signals={"a": 0.5}, volatility_estimate=0.9)
    assert r_low.global_stability_factor >= r_high.global_stability_factor


@pytest.mark.asyncio
async def test_high_regime_instability_reduces_stability():
    fds = FeedbackDampeningService()
    r_low = await fds.dampen(learning_signals={"a": 0.5}, regime_instability=0.1)
    r_high = await fds.dampen(learning_signals={"a": 0.5}, regime_instability=0.9)
    assert r_low.global_stability_factor >= r_high.global_stability_factor


@pytest.mark.asyncio
async def test_high_variance_reduces_stability():
    fds = FeedbackDampeningService()
    r_low = await fds.dampen(learning_signals={"a": 0.5}, allocation_variance=0.1)
    r_high = await fds.dampen(learning_signals={"a": 0.5}, allocation_variance=0.9)
    assert r_low.global_stability_factor >= r_high.global_stability_factor


@pytest.mark.asyncio
async def test_effective_learning_rate_calculated():
    fds = FeedbackDampeningService()
    report = await fds.dampen(
        learning_signals={"a": 0.5, "b": -0.3},
        volatility_estimate=0.5,
        regime_instability=0.3,
        allocation_variance=0.2,
        base_learning_rate=0.1,
    )
    assert len(report.dampened_signals) > 0
    for ds in report.dampened_signals:
        expected_lr = report.global_stability_factor * report.base_learning_rate
        assert abs(ds.effective_learning_rate - expected_lr) < 1e-6


@pytest.mark.asyncio
async def test_dampened_signal_bounds():
    fds = FeedbackDampeningService()
    report = await fds.dampen(
        learning_signals={"a": 10.0, "b": -10.0},
        volatility_estimate=0.0,
    )
    for ds in report.dampened_signals:
        assert abs(ds.dampened_signal) <= abs(ds.raw_signal) + 1e-6


@pytest.mark.asyncio
async def test_global_stability_factor_never_below_01():
    fds = FeedbackDampeningService()
    report = await fds.dampen(
        learning_signals={"a": 0.5},
        volatility_estimate=1.0,
        regime_instability=1.0,
        allocation_variance=1.0,
    )
    assert report.global_stability_factor >= 0.1


@pytest.mark.asyncio
async def test_deterministic():
    fds = FeedbackDampeningService()
    r1 = await fds.dampen(learning_signals={"a": 0.5}, volatility_estimate=0.3)
    r2 = await fds.dampen(learning_signals={"a": 0.5}, volatility_estimate=0.3)
    d1 = r1.model_dump(exclude={"applied_at"})
    d2 = r2.model_dump(exclude={"applied_at"})
    assert d1 == d2
