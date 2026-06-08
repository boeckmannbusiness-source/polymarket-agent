import pytest

from app.services.audit_v3.execution_safety_audit import execution_safety_audit


@pytest.mark.asyncio
async def test_execution_safety_returns_report():
    report = await execution_safety_audit.audit()
    assert report is not None
    assert report.execution_paths is not None


@pytest.mark.asyncio
async def test_execution_safety_score():
    report = await execution_safety_audit.audit()
    assert 0 <= report.score <= 100


@pytest.mark.asyncio
async def test_execution_safety_all_gated():
    report = await execution_safety_audit.audit()
    assert report.all_paths_gated is True


@pytest.mark.asyncio
async def test_execution_safety_paths_count():
    report = await execution_safety_audit.audit()
    assert len(report.execution_paths) >= 5


@pytest.mark.asyncio
async def test_execution_safety_each_path_has_name():
    report = await execution_safety_audit.audit()
    for p in report.execution_paths:
        assert len(p.path_name) > 0


@pytest.mark.asyncio
async def test_execution_safety_tradeservice_gated():
    report = await execution_safety_audit.audit()
    ts = next(p for p in report.execution_paths if "TradeService" in p.path_name)
    assert ts.gated is True


@pytest.mark.asyncio
async def test_execution_safety_executionagent_gated():
    report = await execution_safety_audit.audit()
    ea = next(p for p in report.execution_paths if "ExecutionAgent" in p.path_name)
    assert ea.gated is True


@pytest.mark.asyncio
async def test_execution_safety_scheduler_gated():
    report = await execution_safety_audit.audit()
    sched = next(p for p in report.execution_paths if "Scheduler" in p.path_name)
    assert sched.gated is True


@pytest.mark.asyncio
async def test_execution_safety_emergency_gated():
    report = await execution_safety_audit.audit()
    em = next(p for p in report.execution_paths if "Emergency" in p.path_name)
    assert em.gated is True


@pytest.mark.asyncio
async def test_execution_safety_gate_validate_gated():
    report = await execution_safety_audit.audit()
    gv = next(p for p in report.execution_paths if "ExecutionSafetyGate" in p.path_name)
    assert gv.gated is True


@pytest.mark.asyncio
async def test_execution_safety_control_plane_gated():
    report = await execution_safety_audit.audit()
    cp = next(p for p in report.execution_paths if "ControlPlane" in p.path_name)
    assert cp.gated is True


@pytest.mark.asyncio
async def test_execution_safety_score_100():
    report = await execution_safety_audit.audit()
    assert report.score == 100.0


@pytest.mark.asyncio
async def test_execution_safety_all_gated_true():
    report = await execution_safety_audit.audit()
    assert report.all_paths_gated is True


@pytest.mark.asyncio
async def test_execution_safety_risk_flags_present():
    report = await execution_safety_audit.audit()
    assert len(report.risk_flags) > 0


@pytest.mark.asyncio
async def test_execution_safety_risk_flags_all_gated():
    report = await execution_safety_audit.audit()
    assert any("All execution paths validated as gated" in f for f in report.risk_flags)


@pytest.mark.asyncio
async def test_execution_safety_generated_at():
    report = await execution_safety_audit.audit()
    assert len(report.generated_at) > 0


@pytest.mark.asyncio
async def test_execution_safety_get_latest_returns_none():
    execution_safety_audit._latest = None
    assert await execution_safety_audit.get_latest() is None


@pytest.mark.asyncio
async def test_execution_safety_get_latest_after_audit():
    report = await execution_safety_audit.audit()
    latest = await execution_safety_audit.get_latest()
    assert latest is report
