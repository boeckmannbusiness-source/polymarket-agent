import pytest
from datetime import datetime, timezone

from app.services.audit_v3.micro_capital_readiness_pipeline import micro_capital_readiness_pipeline
from app.schemas.audit_v3 import MicroCapitalReadinessReport


@pytest.mark.asyncio
async def test_pipeline_returns_full_report():
    report = await micro_capital_readiness_pipeline.run()
    assert report is not None
    assert report.audit_id.startswith("audit-v3-")
    assert report.pipeline_status == "completed"


@pytest.mark.asyncio
async def test_pipeline_all_sections_present():
    report = await micro_capital_readiness_pipeline.run()
    assert report.execution_safety is not None
    assert report.capital_protection is not None
    assert report.fail_closed is not None
    assert report.runtime_enforcement is not None
    assert report.operational_readiness is not None
    assert report.micro_capital_readiness is not None


@pytest.mark.asyncio
async def test_pipeline_readiness_report_structure():
    report = await micro_capital_readiness_pipeline.run()
    r = report.micro_capital_readiness
    assert r.classification in ("NOT_READY", "PAPER_READY", "MICRO_CAPITAL_READY")
    assert 0 <= r.overall_score <= 100
    assert len(r.recommendation) > 0


@pytest.mark.asyncio
async def test_pipeline_readiness_scores():
    report = await micro_capital_readiness_pipeline.run()
    r = report.micro_capital_readiness
    assert 0 <= r.execution_safety_score <= 100
    assert 0 <= r.capital_protection_score <= 100
    assert 0 <= r.fail_closed_score <= 100
    assert 0 <= r.runtime_enforcement_score <= 100
    assert 0 <= r.operational_readiness_score <= 100


@pytest.mark.asyncio
async def test_pipeline_classification_not_ready_if_low_exec():
    report = await micro_capital_readiness_pipeline.run()
    r = report.micro_capital_readiness
    if r.execution_safety_score < 70 or r.fail_closed_score < 70:
        assert r.classification == "NOT_READY"


@pytest.mark.asyncio
async def test_pipeline_deterministic():
    r1 = await micro_capital_readiness_pipeline.run()
    r2 = await micro_capital_readiness_pipeline.run()
    r1r = r1.micro_capital_readiness
    r2r = r2.micro_capital_readiness
    assert r1r.overall_score == r2r.overall_score
    assert r1r.classification == r2r.classification


@pytest.mark.asyncio
async def test_pipeline_generated_at():
    report = await micro_capital_readiness_pipeline.run()
    assert len(report.executed_at) > 0
    assert report.micro_capital_readiness.generated_at is not None


@pytest.mark.asyncio
async def test_pipeline_risk_summary_not_empty():
    report = await micro_capital_readiness_pipeline.run()
    assert len(report.micro_capital_readiness.risk_summary) > 0


@pytest.mark.asyncio
async def test_pipeline_classification_logic_all_100():
    from app.schemas.audit_v3 import MicroCapitalReadinessReport
    result = micro_capital_readiness_pipeline._evaluate_readiness(100, 100, 100, 100, 100)
    assert result.classification == "MICRO_CAPITAL_READY"


@pytest.mark.asyncio
async def test_pipeline_classification_logic_70():
    result = micro_capital_readiness_pipeline._evaluate_readiness(70, 70, 70, 70, 70)
    assert result.classification == "PAPER_READY"


@pytest.mark.asyncio
async def test_pipeline_classification_logic_below_70():
    result = micro_capital_readiness_pipeline._evaluate_readiness(69, 100, 100, 100, 100)
    assert result.classification == "NOT_READY"


@pytest.mark.asyncio
async def test_pipeline_classification_logic_fail_closed_below_70():
    result = micro_capital_readiness_pipeline._evaluate_readiness(100, 100, 69, 100, 100)
    assert result.classification == "NOT_READY"


@pytest.mark.asyncio
async def test_pipeline_classification_logic_micro_requires_all_85():
    result = micro_capital_readiness_pipeline._evaluate_readiness(85, 85, 100, 85, 85)
    assert result.classification == "MICRO_CAPITAL_READY"


@pytest.mark.asyncio
async def test_pipeline_classification_logic_micro_requires_fail_closed_100():
    result = micro_capital_readiness_pipeline._evaluate_readiness(100, 100, 99, 100, 100)
    assert result.classification == "PAPER_READY"


@pytest.mark.asyncio
async def test_pipeline_full_run_execution_safety():
    report = await micro_capital_readiness_pipeline.run()
    assert report.execution_safety.score == 100.0


@pytest.mark.asyncio
async def test_pipeline_full_run_capital_protection():
    report = await micro_capital_readiness_pipeline.run()
    assert report.capital_protection.score == 100.0


@pytest.mark.asyncio
async def test_pipeline_full_run_fail_closed():
    report = await micro_capital_readiness_pipeline.run()
    assert report.fail_closed.score == 100.0


@pytest.mark.asyncio
async def test_pipeline_full_run_runtime():
    report = await micro_capital_readiness_pipeline.run()
    assert report.runtime_enforcement.score == 100.0


@pytest.mark.asyncio
async def test_pipeline_full_run_operational():
    report = await micro_capital_readiness_pipeline.run()
    assert report.operational_readiness.overall_score == 100.0


@pytest.mark.asyncio
async def test_pipeline_full_run_gate_score():
    report = await micro_capital_readiness_pipeline.run()
    r = report.micro_capital_readiness
    expected_overall = round(
        (r.execution_safety_score + r.capital_protection_score +
         r.fail_closed_score + r.runtime_enforcement_score +
         r.operational_readiness_score) / 5, 1
    )
    assert r.overall_score == expected_overall


@pytest.mark.asyncio
async def test_pipeline_get_latest_none():
    micro_capital_readiness_pipeline._latest = None
    assert await micro_capital_readiness_pipeline.get_latest() is None


@pytest.mark.asyncio
async def test_pipeline_get_latest_after_run():
    report = await micro_capital_readiness_pipeline.run()
    latest = await micro_capital_readiness_pipeline.get_latest()
    assert latest is report


@pytest.mark.asyncio
async def test_pipeline_recommendation_format():
    result = micro_capital_readiness_pipeline._evaluate_readiness(100, 100, 100, 100, 100)
    assert "SAFE FOR 25-100" in result.recommendation
    result2 = micro_capital_readiness_pipeline._evaluate_readiness(70, 70, 70, 70, 70)
    assert "NOT SAFE" in result2.recommendation
    result3 = micro_capital_readiness_pipeline._evaluate_readiness(69, 100, 100, 100, 100)
    assert "NOT READY" in result3.recommendation


@pytest.mark.asyncio
async def test_pipeline_readiness_report_model_fields():
    report = MicroCapitalReadinessReport()
    assert report.classification == "NOT_READY"
    assert report.overall_score == 0.0


@pytest.mark.asyncio
async def test_pipeline_readiness_with_all_100s():
    result = micro_capital_readiness_pipeline._evaluate_readiness(100, 100, 100, 100, 100)
    assert result.execution_safety_score == 100
    assert result.capital_protection_score == 100
    assert result.fail_closed_score == 100
    assert result.runtime_enforcement_score == 100
    assert result.operational_readiness_score == 100


@pytest.mark.asyncio
async def test_pipeline_micro_capital_requires_fail_closed_100():
    result = micro_capital_readiness_pipeline._evaluate_readiness(85, 85, 100, 85, 85)
    assert result.classification == "MICRO_CAPITAL_READY"
    result = micro_capital_readiness_pipeline._evaluate_readiness(85, 85, 85, 85, 85)
    assert result.classification != "MICRO_CAPITAL_READY"


@pytest.mark.asyncio
async def test_pipeline_classification_no_live_ready():
    result = micro_capital_readiness_pipeline._evaluate_readiness(100, 100, 100, 100, 100)
    assert result.classification != "LIVE_READY"


@pytest.mark.asyncio
async def test_pipeline_stores_all_scores():
    report = await micro_capital_readiness_pipeline.run()
    r = report.micro_capital_readiness
    assert r.execution_safety_score == report.execution_safety.score
    assert r.capital_protection_score == report.capital_protection.score
    assert r.fail_closed_score == report.fail_closed.score
    assert r.runtime_enforcement_score == report.runtime_enforcement.score
    assert r.operational_readiness_score == report.operational_readiness.overall_score


@pytest.mark.asyncio
async def test_pipeline_overall_is_average():
    report = await micro_capital_readiness_pipeline.run()
    r = report.micro_capital_readiness
    avg = (r.execution_safety_score + r.capital_protection_score +
           r.fail_closed_score + r.runtime_enforcement_score +
           r.operational_readiness_score) / 5
    assert r.overall_score == round(avg, 1)
