import pytest
from app.services.control.autonomous_control_pipeline import AutonomousControlPipeline


@pytest.mark.asyncio
async def test_report_structure():
    pipe = AutonomousControlPipeline()
    report = await pipe.run(current_weights={"a": 0.6, "b": 0.4}, previous_weights={"a": 0.5, "b": 0.5})
    assert report.report_id is not None
    assert report.stability is not None
    assert report.dampening is not None
    assert report.drift is not None
    assert report.regime_transitions is not None


@pytest.mark.asyncio
async def test_stability_sub_report_present():
    pipe = AutonomousControlPipeline()
    report = await pipe.run(current_weights={"a": 0.6, "b": 0.4})
    assert report.stability is not None
    assert len(report.stability.allocations) > 0


@pytest.mark.asyncio
async def test_drift_sub_report_present():
    pipe = AutonomousControlPipeline()
    report = await pipe.run(current_weights={"a": 0.6, "b": 0.4}, equilibrium_weights={"a": 0.3, "b": 0.7})
    assert report.drift is not None
    assert report.drift.overall_drift_score >= 0


@pytest.mark.asyncio
async def test_dampening_sub_report_present():
    pipe = AutonomousControlPipeline()
    report = await pipe.run(current_weights={"a": 0.6, "b": 0.4}, learning_signals={"a": 0.5, "b": -0.3})
    assert report.dampening is not None
    assert len(report.dampening.dampened_signals) > 0


@pytest.mark.asyncio
async def test_regime_sub_report_present():
    pipe = AutonomousControlPipeline()
    report = await pipe.run(current_weights={"a": 0.6, "b": 0.4}, current_regime="trending")
    assert report.regime_transitions is not None


@pytest.mark.asyncio
async def test_stabilized_state_list():
    pipe = AutonomousControlPipeline()
    report = await pipe.run(current_weights={"a": 0.6, "b": 0.4}, equilibrium_weights={"a": 0.5, "b": 0.5})
    assert len(report.stabilized_state) > 0
    for s in report.stabilized_state:
        assert s.strategy_id is not None
        assert s.stabilized_weight_pct >= 0


@pytest.mark.asyncio
async def test_summary_string_populated():
    pipe = AutonomousControlPipeline()
    report = await pipe.run(current_weights={"a": 0.6, "b": 0.4})
    assert report.summary != ""


@pytest.mark.asyncio
async def test_empty_inputs():
    pipe = AutonomousControlPipeline()
    report = await pipe.run()
    assert report.report_id is not None
    assert report.summary != ""


@pytest.mark.asyncio
async def test_deterministic():
    pipe = AutonomousControlPipeline()
    r1 = await pipe.run(current_weights={"a": 0.6, "b": 0.4}, previous_weights={"a": 0.5, "b": 0.5}, seed=42)
    r2 = await pipe.run(current_weights={"a": 0.6, "b": 0.4}, previous_weights={"a": 0.5, "b": 0.5}, seed=42)
    d1 = r1.model_dump(exclude={"report_id", "generated_at"})
    d2 = r2.model_dump(exclude={"report_id", "generated_at"})
    for sub in ("stability", "dampening", "drift", "regime_transitions"):
        if d1.get(sub) and d2.get(sub):
            d1[sub].pop("applied_at", None)
            d2[sub].pop("applied_at", None)
            if sub == "drift":
                d1[sub].pop("detected_at", None)
                d2[sub].pop("detected_at", None)
    assert d1 == d2
