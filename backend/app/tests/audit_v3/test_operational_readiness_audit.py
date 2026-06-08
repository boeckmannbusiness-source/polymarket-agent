import pytest

from app.services.audit_v3.operational_readiness_audit import operational_readiness_audit


@pytest.mark.asyncio
async def test_operational_readiness_returns_report():
    report = await operational_readiness_audit.audit()
    assert report is not None
    assert report.details is not None


@pytest.mark.asyncio
async def test_operational_readiness_scores():
    report = await operational_readiness_audit.audit()
    assert 0 <= report.logging_score <= 100
    assert 0 <= report.monitoring_score <= 100
    assert 0 <= report.kill_switch_visibility_score <= 100
    assert 0 <= report.overall_score <= 100


@pytest.mark.asyncio
async def test_operational_readiness_all_100():
    report = await operational_readiness_audit.audit()
    assert report.logging_score == 100.0
    assert report.monitoring_score == 100.0
    assert report.kill_switch_visibility_score == 100.0


@pytest.mark.asyncio
async def test_operational_readiness_logging_checks():
    report = await operational_readiness_audit.audit()
    assert "logging" in report.details
    assert len(report.details["logging"]) >= 4


@pytest.mark.asyncio
async def test_operational_readiness_monitoring_checks():
    report = await operational_readiness_audit.audit()
    assert "monitoring" in report.details
    assert len(report.details["monitoring"]) >= 3


@pytest.mark.asyncio
async def test_operational_readiness_kill_switch_checks():
    report = await operational_readiness_audit.audit()
    assert "kill_switch_visibility" in report.details
    assert len(report.details["kill_switch_visibility"]) >= 3


@pytest.mark.asyncio
async def test_operational_readiness_regime_logged():
    report = await operational_readiness_audit.audit()
    assert report.details["logging"]["regime_logged"] is True


@pytest.mark.asyncio
async def test_operational_readiness_confidence_logged():
    report = await operational_readiness_audit.audit()
    assert report.details["logging"]["confidence_logged"] is True


@pytest.mark.asyncio
async def test_operational_readiness_drift_logged():
    report = await operational_readiness_audit.audit()
    assert report.details["logging"]["drift_logged"] is True


@pytest.mark.asyncio
async def test_operational_readiness_stability_logged():
    report = await operational_readiness_audit.audit()
    assert report.details["logging"]["stability_logged"] is True


@pytest.mark.asyncio
async def test_operational_readiness_decision_reason_logged():
    report = await operational_readiness_audit.audit()
    assert report.details["logging"]["decision_reason_logged"] is True


@pytest.mark.asyncio
async def test_operational_readiness_risk_flags():
    report = await operational_readiness_audit.audit()
    assert any("adequate" in f for f in report.risk_flags)


@pytest.mark.asyncio
async def test_operational_readiness_generated_at():
    report = await operational_readiness_audit.audit()
    assert len(report.generated_at) > 0


@pytest.mark.asyncio
async def test_operational_readiness_get_latest_none():
    operational_readiness_audit._latest = None
    assert await operational_readiness_audit.get_latest() is None


@pytest.mark.asyncio
async def test_operational_readiness_get_latest_after_audit():
    report = await operational_readiness_audit.audit()
    latest = await operational_readiness_audit.get_latest()
    assert latest is report
