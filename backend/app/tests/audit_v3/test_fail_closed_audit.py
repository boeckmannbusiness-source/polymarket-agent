import pytest

from app.services.audit_v3.fail_closed_audit import fail_closed_audit, REDIS_UNAVAILABLE_DETAIL


@pytest.mark.asyncio
async def test_fail_closed_returns_report():
    report = await fail_closed_audit.audit()
    assert report is not None
    assert report.scenarios is not None


@pytest.mark.asyncio
async def test_fail_closed_score():
    report = await fail_closed_audit.audit()
    assert 0 <= report.score <= 100


@pytest.mark.asyncio
async def test_fail_closed_score_100():
    report = await fail_closed_audit.audit()
    assert report.score == 100.0


@pytest.mark.asyncio
async def test_fail_closed_four_scenarios():
    report = await fail_closed_audit.audit()
    assert len(report.scenarios) == 4


@pytest.mark.asyncio
async def test_fail_closed_all_blocked():
    report = await fail_closed_audit.audit()
    assert report.all_blocked is True


@pytest.mark.asyncio
async def test_fail_closed_redis_unavailable():
    report = await fail_closed_audit.audit()
    s = next(x for x in report.scenarios if x.scenario == "Redis unavailable")
    assert s.blocks_execution is True


@pytest.mark.asyncio
async def test_fail_closed_valkey_unavailable():
    report = await fail_closed_audit.audit()
    s = next(x for x in report.scenarios if "Valkey" in x.scenario)
    assert s.blocks_execution is True


@pytest.mark.asyncio
async def test_fail_closed_missing_regime():
    report = await fail_closed_audit.audit()
    s = next(x for x in report.scenarios if "regime" in x.scenario.lower())
    assert s.blocks_execution is True


@pytest.mark.asyncio
async def test_fail_closed_missing_control():
    report = await fail_closed_audit.audit()
    s = next(x for x in report.scenarios if "control" in x.scenario.lower())
    assert s.blocks_execution is True


@pytest.mark.asyncio
async def test_fail_closed_each_has_details():
    report = await fail_closed_audit.audit()
    for s in report.scenarios:
        assert len(s.details) > 0


@pytest.mark.asyncio
async def test_fail_closed_risk_flags_all_blocked():
    report = await fail_closed_audit.audit()
    assert any("All scenarios correctly block" in f for f in report.risk_flags)


@pytest.mark.asyncio
async def test_fail_closed_generated_at():
    report = await fail_closed_audit.audit()
    assert len(report.generated_at) > 0


@pytest.mark.asyncio
async def test_fail_closed_get_latest_none():
    fail_closed_audit._latest = None
    assert await fail_closed_audit.get_latest() is None


@pytest.mark.asyncio
async def test_fail_closed_get_latest_after_audit():
    report = await fail_closed_audit.audit()
    latest = await fail_closed_audit.get_latest()
    assert latest is report


@pytest.mark.asyncio
async def test_fail_closed_redis_detail_constant():
    assert "SystemHaltException" in REDIS_UNAVAILABLE_DETAIL
