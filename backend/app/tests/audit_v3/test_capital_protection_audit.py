import pytest

from app.services.audit_v3.capital_protection_audit import capital_protection_audit


@pytest.mark.asyncio
async def test_capital_protection_returns_report():
    report = await capital_protection_audit.audit()
    assert report is not None
    assert report.limit_checks is not None


@pytest.mark.asyncio
async def test_capital_protection_score():
    report = await capital_protection_audit.audit()
    assert 0 <= report.score <= 100


@pytest.mark.asyncio
async def test_capital_protection_score_100():
    report = await capital_protection_audit.audit()
    assert report.score == 100.0


@pytest.mark.asyncio
async def test_capital_protection_three_limits():
    report = await capital_protection_audit.audit()
    assert len(report.limit_checks) == 3


@pytest.mark.asyncio
async def test_capital_protection_position_limit():
    report = await capital_protection_audit.audit()
    pl = next(c for c in report.limit_checks if "Position" in c.limit_name)
    assert pl.can_exceed is False


@pytest.mark.asyncio
async def test_capital_protection_exposure_limit():
    report = await capital_protection_audit.audit()
    el = next(c for c in report.limit_checks if "Exposure" in c.limit_name)
    assert el.can_exceed is False


@pytest.mark.asyncio
async def test_capital_protection_drawdown_limit():
    report = await capital_protection_audit.audit()
    dl = next(c for c in report.limit_checks if "Drawdown" in c.limit_name)
    assert dl.can_exceed is False


@pytest.mark.asyncio
async def test_capital_protection_kill_switch_triggers():
    report = await capital_protection_audit.audit()
    assert report.kill_switch_triggers is True


@pytest.mark.asyncio
async def test_capital_protection_limit_values():
    report = await capital_protection_audit.audit()
    pl = next(c for c in report.limit_checks if "Position" in c.limit_name)
    assert pl.limit_value == 10.0
    el = next(c for c in report.limit_checks if "Exposure" in c.limit_name)
    assert el.limit_value == 0.15


@pytest.mark.asyncio
async def test_capital_protection_risk_flags_all_enforced():
    report = await capital_protection_audit.audit()
    assert any("All capital limits enforced" in f for f in report.risk_flags)


@pytest.mark.asyncio
async def test_capital_protection_generated_at():
    report = await capital_protection_audit.audit()
    assert len(report.generated_at) > 0


@pytest.mark.asyncio
async def test_capital_protection_get_latest_none():
    capital_protection_audit._latest = None
    assert await capital_protection_audit.get_latest() is None


@pytest.mark.asyncio
async def test_capital_protection_get_latest_after_audit():
    report = await capital_protection_audit.audit()
    latest = await capital_protection_audit.get_latest()
    assert latest is report


@pytest.mark.asyncio
async def test_capital_protection_custom_limits():
    report = await capital_protection_audit.audit(
        position_limit_eur=25.0, exposure_limit_pct=0.25, drawdown_limit=0.20
    )
    assert report.score == 100.0
