import pytest
from app.services.control.stability_controller_service import StabilityController


@pytest.mark.asyncio
async def test_max_delta_weight_enforcement():
    sc = StabilityController()
    cw = {"a": 1.0, "b": 0.0}
    pw = {"a": 0.0, "b": 1.0}
    report = await sc.apply_stability_constraints(current_weights=cw, previous_weights=pw, max_delta_weight=0.02)
    for a in report.allocations:
        prev = pw.get(a.strategy_id, 0.0) * 100
        assert abs(a.stabilized_weight_pct - prev) <= 2.0 + 1e-4 or abs(a.stabilized_weight_pct - prev) < 0.5


@pytest.mark.asyncio
async def test_ema_smoothing_correctness():
    sc = StabilityController()
    cw = {"a": 0.8, "b": 0.2}
    pw = {"a": 0.5, "b": 0.5}
    report = await sc.apply_stability_constraints(current_weights=cw, previous_weights=pw, ema_smoothing_factor=0.3)
    for a in report.allocations:
        assert 0 <= a.stabilized_weight_pct <= 100
    assert abs(sum(a.stabilized_weight_pct for a in report.allocations) - 100.0) < 1.0


@pytest.mark.asyncio
async def test_turnover_cap_enforced():
    sc = StabilityController()
    cw = {f"s{i}": 1.0 for i in range(10)}
    pw = {f"s{i}": 0.0 for i in range(10)}
    report = await sc.apply_stability_constraints(current_weights=cw, previous_weights=pw, max_delta_weight=0.01, total_turnover_cap=10.0)
    assert report.total_turnover_pct <= 10.0 * 100 + 1e-4


@pytest.mark.asyncio
async def test_regime_probability_smoothing():
    sc = StabilityController()
    rp = {"trending": 0.9, "mean_reverting": 0.1}
    prp = {"trending": 0.5, "mean_reverting": 0.5}
    report = await sc.apply_stability_constraints(current_weights={}, regime_probabilities=rp, previous_regime_probabilities=prp, ema_smoothing_factor=0.3)
    for k in rp:
        expected = 0.3 * rp[k] + 0.7 * prp[k]
        assert abs(report.regime_probabilities_stabilized.get(k, 0) - expected) < 1e-2
    total = sum(report.regime_probabilities_stabilized.values())
    assert abs(total - 1.0) < 1e-4


@pytest.mark.asyncio
async def test_risk_penalty_smoothing():
    sc = StabilityController()
    rp = {"a": 0.8, "b": 0.2}
    report = await sc.apply_stability_constraints(current_weights={}, risk_penalties=rp, ema_smoothing_factor=0.3)
    for k in rp:
        assert k in report.risk_penalties_stabilized
        assert report.risk_penalties_stabilized[k] > 0


@pytest.mark.asyncio
async def test_empty_inputs_produce_safe_defaults():
    sc = StabilityController()
    report = await sc.apply_stability_constraints(current_weights={})
    assert report.total_turnover_pct == 0.0
    assert len(report.allocations) == 0
    assert report.applied_at != ""


@pytest.mark.asyncio
async def test_allocation_stability_score_lower_is_better():
    sc = StabilityController()
    cw = {"a": 1.0}
    pw = {"a": 1.0}
    report_same = await sc.apply_stability_constraints(current_weights=cw, previous_weights=pw)
    cw2 = {"a": 1.0}
    pw2 = {"a": 0.0}
    report_diff = await sc.apply_stability_constraints(current_weights=cw2, previous_weights=pw2)
    assert report_same.total_turnover_pct <= report_diff.total_turnover_pct


@pytest.mark.asyncio
async def test_delta_weight_capped_at_max():
    sc = StabilityController()
    cw = {"a": 1.0}
    pw = {"a": 0.0}
    report = await sc.apply_stability_constraints(current_weights=cw, previous_weights=pw, max_delta_weight=0.02)
    for a in report.allocations:
        delta = abs(a.stabilized_weight_pct - pw[a.strategy_id] * 100)
        assert delta <= 2.0 + 1e-2 or a.strategy_id not in pw


@pytest.mark.asyncio
async def test_deterministic_given_seed():
    sc = StabilityController()
    cw = {"a": 0.7, "b": 0.3}
    pw = {"a": 0.5, "b": 0.5}
    r1 = await sc.apply_stability_constraints(current_weights=cw, previous_weights=pw)
    r2 = await sc.apply_stability_constraints(current_weights=cw, previous_weights=pw)
    d1 = r1.model_dump(exclude={"applied_at"})
    d2 = r2.model_dump(exclude={"applied_at"})
    assert d1 == d2


@pytest.mark.asyncio
async def test_ema_smoothing_factor_default():
    sc = StabilityController()
    report = await sc.apply_stability_constraints(current_weights={"a": 1.0}, previous_weights={"a": 0.0})
    assert report.ema_smoothing_factor == 0.3
