import pytest

from app.services.audit_v3.runtime_enforcement_audit import runtime_enforcement_audit


@pytest.mark.asyncio
async def test_runtime_enforcement_returns_report():
    report = await runtime_enforcement_audit.audit()
    assert report is not None
    assert report.checks is not None


@pytest.mark.asyncio
async def test_runtime_enforcement_score():
    report = await runtime_enforcement_audit.audit()
    assert 0 <= report.score <= 100


@pytest.mark.asyncio
async def test_runtime_enforcement_score_100():
    report = await runtime_enforcement_audit.audit()
    assert report.score == 100.0


@pytest.mark.asyncio
async def test_runtime_enforcement_four_checks():
    report = await runtime_enforcement_audit.audit()
    assert len(report.checks) == 4


@pytest.mark.asyncio
async def test_runtime_enforcement_all_blocked():
    report = await runtime_enforcement_audit.audit()
    assert report.all_blocked is True


@pytest.mark.asyncio
async def test_runtime_enforcement_drift_blocked():
    report = await runtime_enforcement_audit.audit()
    c = next(x for x in report.checks if "drift" in x.check_name.lower())
    assert c.blocked is True


@pytest.mark.asyncio
async def test_runtime_enforcement_stability_blocked():
    report = await runtime_enforcement_audit.audit()
    c = next(x for x in report.checks if "stability" in x.check_name.lower())
    assert c.blocked is True


@pytest.mark.asyncio
async def test_runtime_enforcement_control_failure_blocked():
    report = await runtime_enforcement_audit.audit()
    c = next(x for x in report.checks if "CONTROL_FAILURE" in x.check_name)
    assert c.blocked is True


@pytest.mark.asyncio
async def test_runtime_enforcement_regime_confidence_blocked():
    report = await runtime_enforcement_audit.audit()
    c = next(x for x in report.checks if "regime" in x.check_name.lower())
    assert c.blocked is True


@pytest.mark.asyncio
async def test_runtime_enforcement_each_has_details():
    report = await runtime_enforcement_audit.audit()
    for c in report.checks:
        assert len(c.details) > 0


@pytest.mark.asyncio
async def test_runtime_enforcement_risk_flags():
    report = await runtime_enforcement_audit.audit()
    assert any("All runtime enforcement" in f for f in report.risk_flags)


@pytest.mark.asyncio
async def test_runtime_enforcement_generated_at():
    report = await runtime_enforcement_audit.audit()
    assert len(report.generated_at) > 0


@pytest.mark.asyncio
async def test_runtime_enforcement_get_latest_none():
    runtime_enforcement_audit._latest = None
    assert await runtime_enforcement_audit.get_latest() is None


@pytest.mark.asyncio
async def test_runtime_enforcement_get_latest_after_audit():
    report = await runtime_enforcement_audit.audit()
    latest = await runtime_enforcement_audit.get_latest()
    assert latest is report
