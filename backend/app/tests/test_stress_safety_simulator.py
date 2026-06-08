import pytest
from app.services.audit_v2.stress_safety_simulator import StressSafetySimulator


@pytest.fixture
def service():
    return StressSafetySimulator()


@pytest.mark.asyncio
async def test_simulate_returns_report(service):
    report = await service.simulate()
    assert report.scenario_results is not None
    assert len(report.scenario_results) == 3
    assert report.generated_at != ""


@pytest.mark.asyncio
async def test_simulate_all_three_scenarios_present(service):
    report = await service.simulate()
    types = [r.scenario_type for r in report.scenario_results]
    assert "Regime Misclassification" in types
    assert "Correlation Shock" in types
    assert "Volatility Spike" in types


@pytest.mark.asyncio
async def test_simulate_scenario_ids_correct(service):
    report = await service.simulate()
    ids = [r.scenario_id for r in report.scenario_results]
    assert "regime_misclassification" in ids
    assert "correlation_shock" in ids
    assert "volatility_spike" in ids


@pytest.mark.asyncio
async def test_simulate_worst_case_identified(service):
    report = await service.simulate()
    assert report.worst_case_scenario != ""
    worst = next(r for r in report.scenario_results
                 if r.scenario_type == report.worst_case_scenario)
    assert worst.max_drawdown_estimate >= 0


@pytest.mark.asyncio
async def test_simulate_worst_case_is_worst(service):
    report = await service.simulate()
    if report.scenario_results:
        max_dd = max(r.max_drawdown_estimate for r in report.scenario_results)
        worst = next(r for r in report.scenario_results
                     if r.scenario_type == report.worst_case_scenario)
        assert worst.max_drawdown_estimate == max_dd


@pytest.mark.asyncio
async def test_simulate_drawdown_estimates_reasonable(service):
    report = await service.simulate()
    for r in report.scenario_results:
        assert 0 <= r.max_drawdown_estimate <= 100


@pytest.mark.asyncio
async def test_simulate_allocation_deviation_reasonable(service):
    report = await service.simulate()
    for r in report.scenario_results:
        assert r.allocation_deviation >= 0


@pytest.mark.asyncio
async def test_simulate_recovery_sensitivity_valid(service):
    report = await service.simulate()
    for r in report.scenario_results:
        assert r.recovery_sensitivity in ("low", "medium", "high")


@pytest.mark.asyncio
async def test_simulate_stress_score_computed(service):
    report = await service.simulate()
    assert 0 <= report.overall_stress_score <= 100


@pytest.mark.asyncio
async def test_simulate_default_allocations_work(service):
    report = await service.simulate()
    assert len(report.scenario_results) == 3


@pytest.mark.asyncio
async def test_simulate_custom_allocations(service):
    baseline = {"momentum_strat": 0.5, "reversion_strat": 0.5}
    report = await service.simulate(baseline_allocations=baseline)
    regime_result = next(r for r in report.scenario_results
                         if r.scenario_id == "regime_misclassification")
    assert regime_result.allocation_deviation > 0


@pytest.mark.asyncio
async def test_simulate_regime_misclassification_details(service):
    baseline = {"momentum_strat": 0.4, "reversion_strat": 0.3, "neutral": 0.3}
    report = await service.simulate(baseline_allocations=baseline)
    regime_result = next(r for r in report.scenario_results
                         if r.scenario_id == "regime_misclassification")
    assert "momentum_strat" in regime_result.details
    assert "reversion_strat" in regime_result.details


@pytest.mark.asyncio
async def test_simulate_correlation_shock_computation(service):
    corr = {
        "a": {"a": 1.0, "b": 0.2, "c": 0.3},
        "b": {"a": 0.2, "b": 1.0, "c": 0.1},
        "c": {"a": 0.3, "b": 0.1, "c": 1.0},
    }
    baseline = {"a": 0.4, "b": 0.3, "c": 0.3}
    report = await service.simulate(
        baseline_allocations=baseline, correlation_matrix=corr
    )
    shock_result = next(r for r in report.scenario_results
                        if r.scenario_id == "correlation_shock")
    assert "original_avg_correlation" in shock_result.details
    assert shock_result.details["shocked_correlation"] >= shock_result.details["original_avg_correlation"]


@pytest.mark.asyncio
async def test_simulate_volatility_spike_computation(service):
    variances = {"a": 0.02, "b": 0.03, "c": 0.04}
    baseline = {"a": 0.4, "b": 0.3, "c": 0.3}
    report = await service.simulate(
        baseline_allocations=baseline, return_variances=variances
    )
    vol_result = next(r for r in report.scenario_results
                      if r.scenario_id == "volatility_spike")
    assert "original_avg_volatility" in vol_result.details
    assert vol_result.details["volatility_multiplier"] > 1.0


@pytest.mark.asyncio
async def test_simulate_risk_flags_for_high_drawdown(service):
    report = await service.simulate(baseline_allocations={"momentum_a": 1.0})
    has_flags = len(report.risk_flags) > 0
    assert has_flags or report.overall_stress_score >= 40


@pytest.mark.asyncio
async def test_get_latest_returns_none_initially(service):
    assert await service.get_latest() is None


@pytest.mark.asyncio
async def test_get_latest_after_simulate(service):
    report = await service.simulate()
    latest = await service.get_latest()
    assert latest is not None
    assert latest.generated_at == report.generated_at


@pytest.mark.asyncio
async def test_simulate_deterministic_with_seed(service):
    baseline = {"strat_a": 0.5, "strat_b": 0.5}
    report1 = await service.simulate(baseline_allocations=baseline)
    report2 = await service.simulate(baseline_allocations=baseline)
    assert len(report1.scenario_results) == len(report2.scenario_results)
    for r1, r2 in zip(report1.scenario_results, report2.scenario_results):
        assert r1.max_drawdown_estimate == r2.max_drawdown_estimate
        assert r1.allocation_deviation == r2.allocation_deviation
