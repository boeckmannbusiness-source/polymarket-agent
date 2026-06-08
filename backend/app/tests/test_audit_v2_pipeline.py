import pytest
from app.services.audit_v2.autonomous_safety_audit_pipeline import AutonomousSafetyAuditPipeline


@pytest.fixture
def pipeline():
    return AutonomousSafetyAuditPipeline()


@pytest.mark.asyncio
async def test_pipeline_returns_complete_report(pipeline):
    report = await pipeline.run()
    assert report.audit_id != ""
    assert report.executed_at != ""
    assert report.pipeline_status == "completed"


@pytest.mark.asyncio
async def test_pipeline_all_sections_present(pipeline):
    report = await pipeline.run()
    assert report.system_safety is not None
    assert report.data_integrity is not None
    assert report.feedback_cycles is not None
    assert report.stress_safety is not None
    assert report.production_gate is not None


@pytest.mark.asyncio
async def test_pipeline_system_safety_has_components(pipeline):
    report = await pipeline.run()
    assert len(report.system_safety.components) > 0
    assert len(report.system_safety.critical_paths) > 0


@pytest.mark.asyncio
async def test_pipeline_data_integrity_has_signals(pipeline):
    report = await pipeline.run()
    assert len(report.data_integrity.signals) > 0
    assert report.data_integrity.overall_data_quality_score >= 0


@pytest.mark.asyncio
async def test_pipeline_feedback_cycles_detected(pipeline):
    report = await pipeline.run()
    assert report.feedback_cycles.cycles is not None
    assert report.feedback_cycles.overall_risk_level in ("LOW", "MEDIUM", "HIGH")


@pytest.mark.asyncio
async def test_pipeline_stress_safety_has_scenarios(pipeline):
    report = await pipeline.run()
    assert len(report.stress_safety.scenario_results) == 3
    assert report.stress_safety.worst_case_scenario != ""


@pytest.mark.asyncio
async def test_pipeline_production_gate_classified(pipeline):
    report = await pipeline.run()
    assert report.production_gate.classification in (
        "NOT_READY", "PAPER_READY", "MICRO_CAPITAL_READY", "LIVE_READY"
    )
    assert report.production_gate.overall_score >= 0


@pytest.mark.asyncio
async def test_pipeline_classification_matches_scores(pipeline):
    report = await pipeline.run()
    gate = report.production_gate
    if gate.classification == "NOT_READY":
        assert gate.stability_score < 40 or gate.data_score < 40 or gate.stress_score < 40
    elif gate.classification == "LIVE_READY":
        assert gate.stability_score >= 80 and gate.data_score >= 80 and gate.stress_score >= 80


@pytest.mark.asyncio
async def test_pipeline_audit_id_unique(pipeline):
    report1 = await pipeline.run()
    report2 = await pipeline.run()
    assert report1.audit_id != report2.audit_id


@pytest.mark.asyncio
async def test_pipeline_stress_scenario_types(pipeline):
    report = await pipeline.run()
    types = [s.scenario_type for s in report.stress_safety.scenario_results]
    assert "Regime Misclassification" in types
    assert "Correlation Shock" in types
    assert "Volatility Spike" in types


@pytest.mark.asyncio
async def test_pipeline_deterministic_output(pipeline):
    report1 = await pipeline.run()
    report2 = await pipeline.run()
    # Core structure should be identical (same components, same cycles)
    assert len(report1.system_safety.components) == len(report2.system_safety.components)
    assert len(report1.feedback_cycles.cycles) == len(report2.feedback_cycles.cycles)
    assert report1.data_integrity.overall_data_quality_score == report2.data_integrity.overall_data_quality_score


@pytest.mark.asyncio
async def test_pipeline_gate_recommendation_present(pipeline):
    report = await pipeline.run()
    assert report.production_gate.recommendation != ""
    assert len(report.production_gate.recommendation) > 20


@pytest.mark.asyncio
async def test_pipeline_gate_risk_summary_present(pipeline):
    report = await pipeline.run()
    assert report.production_gate.risk_summary != ""
    assert len(report.production_gate.risk_summary) > 10


@pytest.mark.asyncio
async def test_pipeline_system_safety_risk_flags(pipeline):
    report = await pipeline.run()
    assert len(report.system_safety.risk_flags) >= 0
    for flag in report.system_safety.risk_flags:
        assert isinstance(flag, str)


@pytest.mark.asyncio
async def test_pipeline_data_integrity_source_types(pipeline):
    report = await pipeline.run()
    types = {s.source_type for s in report.data_integrity.signals}
    assert "internal_computed" in types


@pytest.mark.asyncio
async def test_pipeline_stress_score_range(pipeline):
    report = await pipeline.run()
    assert 0 <= report.stress_safety.overall_stress_score <= 100


@pytest.mark.asyncio
async def test_get_latest_returns_none_initially(pipeline):
    assert await pipeline.get_latest() is None


@pytest.mark.asyncio
async def test_get_latest_after_run(pipeline):
    report = await pipeline.run()
    latest = await pipeline.get_latest()
    assert latest is not None
    assert latest.audit_id == report.audit_id
    assert latest.executed_at == report.executed_at


@pytest.mark.asyncio
async def test_pipeline_spof_consistency(pipeline):
    report = await pipeline.run()
    spofs = report.system_safety.single_points_of_failure
    spof_flags = [f for f in report.system_safety.risk_flags if "SPOF:" in f]
    assert len(spof_flags) == len(spofs)


@pytest.mark.asyncio
async def test_pipeline_feedback_cycle_consistency(pipeline):
    report = await pipeline.run()
    cycles = report.feedback_cycles.cycles
    if cycles:
        for c in cycles:
            assert c.cycle_length == len(c.cycle) - 1
            assert c.risk_level in ("LOW", "MEDIUM", "HIGH")
