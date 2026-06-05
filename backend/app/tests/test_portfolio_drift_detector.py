import pytest
from app.services.control.portfolio_drift_detector import PortfolioDriftDetector


@pytest.mark.asyncio
async def test_allocation_drift_correctness():
    pdd = PortfolioDriftDetector()
    cw = {"a": 0.6, "b": 0.4}
    eq = {"a": 0.5, "b": 0.5}
    report = await pdd.detect_drift(current_weights=cw, equilibrium_weights=eq)
    assert report.allocation_drift > 0
    assert report.allocation_drift < 100


@pytest.mark.asyncio
async def test_regime_drift_calculation():
    pdd = PortfolioDriftDetector()
    pred = {"trending": 0.8, "mean_reverting": 0.2}
    real = {"trending": 0.5, "mean_reverting": 0.5}
    report = await pdd.detect_drift(current_weights={"a": 1.0}, predicted_regime_probs=pred, realized_regime_probs=real)
    assert report.regime_drift > 0
    assert report.regime_drift < 100


@pytest.mark.asyncio
async def test_risk_drift():
    pdd = PortfolioDriftDetector()
    cur_cov = {"a": {"b": 0.5}, "b": {"a": 0.5}}
    base_cov = {"a": {"b": 0.1}, "b": {"a": 0.1}}
    report = await pdd.detect_drift(current_weights={"a": 1.0}, current_covariance=cur_cov, baseline_covariance=base_cov)
    assert report.risk_drift > 0
    assert report.risk_drift < 100


@pytest.mark.asyncio
async def test_drift_sources_populated():
    pdd = PortfolioDriftDetector()
    cw = {"a": 0.6, "b": 0.4}
    eq = {"a": 0.5, "b": 0.5}
    report = await pdd.detect_drift(current_weights=cw, equilibrium_weights=eq)
    assert len(report.drift_sources) > 0


@pytest.mark.asyncio
async def test_trend_classification_stable():
    pdd = PortfolioDriftDetector()
    report = await pdd.detect_drift(current_weights={"a": 1.0}, equilibrium_weights={"a": 0.99})
    assert report.drift_trend in ("stable", "watch", "diverging")


@pytest.mark.asyncio
async def test_trend_classification_diverging():
    pdd = PortfolioDriftDetector()
    cw = {"a": 1.0}
    eq = {"a": 0.0, "b": 0.0, "c": 0.0, "d": 0.0, "e": 1.0}
    report = await pdd.detect_drift(current_weights=cw, equilibrium_weights=eq)
    assert report.drift_trend in ("stable", "watch", "diverging")


@pytest.mark.asyncio
async def test_risk_warnings_at_threshold():
    pdd = PortfolioDriftDetector()
    cw = {"a": 1.0}
    eq = {"a": 0.0, "b": 1.0}
    report = await pdd.detect_drift(current_weights=cw, equilibrium_weights=eq)
    assert isinstance(report.risk_warnings, list)


@pytest.mark.asyncio
async def test_no_drift_with_identical_inputs():
    pdd = PortfolioDriftDetector()
    report = await pdd.detect_drift(current_weights={"a": 0.5, "b": 0.5}, equilibrium_weights={"a": 0.5, "b": 0.5})
    assert report.overall_drift_score < 1.0


@pytest.mark.asyncio
async def test_deterministic():
    pdd = PortfolioDriftDetector()
    cw = {"a": 0.6, "b": 0.4}
    eq = {"a": 0.5, "b": 0.5}
    r1 = await pdd.detect_drift(current_weights=cw, equilibrium_weights=eq)
    r2 = await pdd.detect_drift(current_weights=cw, equilibrium_weights=eq)
    d1 = r1.model_dump(exclude={"detected_at"})
    d2 = r2.model_dump(exclude={"detected_at"})
    assert d1 == d2
