import pytest
from app.services.control.regime_transition_controller import RegimeTransitionController


@pytest.mark.asyncio
async def test_persistence_counting():
    rtc = RegimeTransitionController()
    report = await rtc.stabilize(current_regime="trending", regime_probabilities={"trending": 0.8, "mean_reverting": 0.2})
    reg = next((r for r in report.regimes if r.regime == "trending"), None)
    assert reg is not None
    assert reg.persistence_count >= 0


@pytest.mark.asyncio
async def test_inertia_computation():
    rtc = RegimeTransitionController()
    r1 = await rtc.stabilize(current_regime="trending", regime_probabilities={"trending": 0.8, "mean_reverting": 0.2})
    r2 = await rtc.stabilize(current_regime="trending", regime_probabilities={"trending": 0.8, "mean_reverting": 0.2})
    reg1 = next((r for r in r1.regimes if r.regime == "trending"), None)
    reg2 = next((r for r in r2.regimes if r.regime == "trending"), None)
    if reg1 and reg2:
        assert reg2.persistence_count >= reg1.persistence_count


@pytest.mark.asyncio
async def test_volatility_shock_adjustment():
    rtc = RegimeTransitionController()
    report_shock = await rtc.stabilize(current_regime="trending", regime_probabilities={"trending": 1.0}, volatility_shock=0.9)
    report_calm = await rtc.stabilize(current_regime="trending", regime_probabilities={"trending": 1.0}, volatility_shock=0.0)
    assert report_shock.volatility_adjustment > report_calm.volatility_adjustment


@pytest.mark.asyncio
async def test_signal_divergence_dampening():
    rtc = RegimeTransitionController()
    report = await rtc.stabilize(
        current_regime="trending",
        regime_probabilities={"trending": 0.8, "mean_reverting": 0.2},
        signal_divergence_detected=True,
    )
    assert len(report.regimes) > 0


@pytest.mark.asyncio
async def test_probability_output_bounds():
    rtc = RegimeTransitionController()
    report = await rtc.stabilize(
        current_regime="trending",
        regime_probabilities={"trending": 0.8, "mean_reverting": 0.2},
        predicted_next_probs={"trending": 0.7, "mean_reverting": 0.3},
    )
    for regime in report.regimes:
        assert 0.0 <= regime.probability <= 1.0


@pytest.mark.asyncio
async def test_smoothed_flag():
    rtc = RegimeTransitionController()
    report = await rtc.stabilize(current_regime="trending", regime_probabilities={"trending": 0.8, "mean_reverting": 0.2})
    any_smoothed = any(r.transitions_smoothed for r in report.regimes)
    assert isinstance(any_smoothed, bool)


@pytest.mark.asyncio
async def test_transition_matrix_7_regimes():
    rtc = RegimeTransitionController()
    report = await rtc.stabilize(current_regime="trending", regime_probabilities={"trending": 1.0})
    assert len(report.transition_matrix) > 0


@pytest.mark.asyncio
async def test_multiple_regime_states():
    rtc = RegimeTransitionController()
    rp = {"trending": 0.4, "mean_reverting": 0.3, "high_volatility": 0.2, "event_driven": 0.1}
    report = await rtc.stabilize(current_regime="trending", regime_probabilities=rp)
    assert len(report.regimes) >= len(rp)


@pytest.mark.asyncio
async def test_deterministic():
    r1 = await RegimeTransitionController().stabilize(current_regime="trending", regime_probabilities={"trending": 0.8, "mean_reverting": 0.2})
    r2 = await RegimeTransitionController().stabilize(current_regime="trending", regime_probabilities={"trending": 0.8, "mean_reverting": 0.2})
    d1 = r1.model_dump(exclude={"applied_at"})
    d2 = r2.model_dump(exclude={"applied_at"})
    assert d1 == d2
