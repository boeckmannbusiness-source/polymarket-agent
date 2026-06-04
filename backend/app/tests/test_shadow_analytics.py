import pytest
import math
from datetime import datetime, timezone
from unittest.mock import patch

from app.services.shadow.shadow_analytics_service import (
    ShadowAnalyticsService,
    analytics_service,
)
from app.services.shadow.shadow_execution_service import (
    ShadowExecutionService,
    ShadowExecution,
    shadow_execution_service,
)


@pytest.fixture(autouse=True)
def _no_redis():
    with patch("app.services.shadow.shadow_analytics_service.ShadowAnalyticsService._safe_redis", return_value=None):
        with patch("app.services.shadow.shadow_execution_service.ShadowExecutionService._safe_redis", return_value=None):
            yield


def _service_with_executions(execs: list[ShadowExecution]) -> ShadowAnalyticsService:
    shadow_execution_service.reset()
    for e in execs:
        shadow_execution_service._executions[e.id] = e
    svc = ShadowAnalyticsService()
    svc._executions = shadow_execution_service.get_all_executions()
    return svc


def _make_exec(
    exec_id: str,
    strategy: str,
    entry_price: float,
    exit_price: float | None = None,
    direction: str = "buy",
    pnl: float | None = None,
    status: str = "closed",
    entry_ts: str | None = None,
    exit_ts: str | None = None,
) -> ShadowExecution:
    now = datetime.now(timezone.utc).isoformat()
    return ShadowExecution(
        id=exec_id,
        signal_id=f"sig-{exec_id}",
        market_id="mkt-1",
        strategy=strategy,
        direction=direction,
        outcome="YES",
        size=10.0,
        entry_price=entry_price,
        entry_timestamp=entry_ts or now,
        exit_price=exit_price,
        exit_timestamp=exit_ts or now,
        realized_pnl=pnl,
        status=status,
    )


@pytest.mark.asyncio
async def test_sharpe_calculation():
    execs = [
        _make_exec("1", "alpha", 0.5, 0.6, pnl=1.0),
        _make_exec("2", "alpha", 0.5, 0.3, pnl=-2.0),
        _make_exec("3", "alpha", 0.5, 0.7, pnl=2.0),
        _make_exec("4", "alpha", 0.5, 0.55, pnl=0.5),
        _make_exec("5", "alpha", 0.5, 0.8, pnl=3.0),
    ]
    svc = _service_with_executions(execs)
    result = await svc.get_strategy_analytics("alpha")
    assert result.sharpe_ratio != 0.0
    assert result.sharpe_ratio > -10
    assert result.sharpe_ratio < 10


@pytest.mark.asyncio
async def test_sortino_calculation():
    execs = [
        _make_exec("1", "alpha", 0.5, 0.6, pnl=1.0),
        _make_exec("2", "alpha", 0.5, 0.3, pnl=-2.0),
        _make_exec("3", "alpha", 0.5, 0.7, pnl=2.0),
        _make_exec("4", "alpha", 0.5, 0.55, pnl=0.5),
        _make_exec("5", "alpha", 0.5, 0.8, pnl=3.0),
    ]
    svc = _service_with_executions(execs)
    result = await svc.get_strategy_analytics("alpha")
    assert result.sortino_ratio != 0.0
    assert result.sortino_ratio > -10
    assert result.sortino_ratio < 10


@pytest.mark.asyncio
async def test_max_drawdown():
    execs = [
        _make_exec("1", "alpha", 0.5, 0.6, pnl=1.0),
        _make_exec("2", "alpha", 0.5, 0.3, pnl=-5.0),
        _make_exec("3", "alpha", 0.5, 0.7, pnl=2.0),
        _make_exec("4", "alpha", 0.5, 0.55, pnl=0.5),
        _make_exec("5", "alpha", 0.5, 0.8, pnl=3.0),
    ]
    svc = _service_with_executions(execs)
    result = await svc.get_strategy_analytics("alpha")
    assert result.max_drawdown > 0.0
    assert result.max_drawdown <= 1.0


@pytest.mark.asyncio
async def test_profit_factor():
    execs = [
        _make_exec("1", "alpha", 0.5, 0.6, pnl=2.0),
        _make_exec("2", "alpha", 0.5, 0.3, pnl=-1.0),
        _make_exec("3", "alpha", 0.5, 0.7, pnl=3.0),
    ]
    svc = _service_with_executions(execs)
    result = await svc.get_strategy_analytics("alpha")
    assert result.profit_factor == pytest.approx(5.0, rel=0.1)  # (2+3) / 1


@pytest.mark.asyncio
async def test_expectancy():
    execs = [
        _make_exec("1", "alpha", 0.5, 0.6, pnl=2.0),
        _make_exec("2", "alpha", 0.5, 0.3, pnl=-1.0),
        _make_exec("3", "alpha", 0.5, 0.7, pnl=3.0),
    ]
    svc = _service_with_executions(execs)
    result = await svc.get_strategy_analytics("alpha")
    avg = (2.0 + -1.0 + 3.0) / 3
    wins = 2
    losses = 1
    expected = (wins * avg - losses * abs(avg)) / 3
    assert result.expectancy == pytest.approx(expected, rel=0.1)


@pytest.mark.asyncio
async def test_win_rate():
    execs = [
        _make_exec("1", "alpha", 0.5, 0.6, pnl=1.0),
        _make_exec("2", "alpha", 0.5, 0.3, pnl=-2.0),
        _make_exec("3", "alpha", 0.5, 0.7, pnl=3.0),
    ]
    svc = _service_with_executions(execs)
    result = await svc.get_strategy_analytics("alpha")
    assert result.win_rate == pytest.approx(2 / 3, rel=0.01)


@pytest.mark.asyncio
async def test_total_signals_and_closed():
    execs = [
        _make_exec("1", "alpha", 0.5, 0.6, pnl=1.0, status="closed"),
        _make_exec("2", "alpha", 0.5, None, pnl=None, status="open"),
        _make_exec("3", "alpha", 0.5, 0.7, pnl=3.0, status="closed"),
    ]
    svc = _service_with_executions(execs)
    result = await svc.get_strategy_analytics("alpha")
    assert result.total_signals == 3
    assert result.closed_positions == 2
    assert result.executed_signals == 3


@pytest.mark.asyncio
async def test_realized_and_unrealized_pnl():
    execs = [
        _make_exec("1", "alpha", 0.5, 0.6, pnl=1.0, status="closed"),
        _make_exec("2", "alpha", 0.5, None, pnl=None, status="open"),
    ]
    execs[1].unrealized_pnl = 2.0
    svc = _service_with_executions(execs)
    result = await svc.get_strategy_analytics("alpha")
    assert result.realized_pnl == 1.0
    assert result.unrealized_pnl == 2.0
    assert result.total_pnl == 3.0


@pytest.mark.asyncio
async def test_average_holding_time():
    ts1 = "2026-01-01T00:00:00+00:00"
    ts2 = "2026-01-02T00:00:00+00:00"
    execs = [
        _make_exec("1", "alpha", 0.5, 0.6, pnl=1.0, entry_ts=ts1, exit_ts=ts2),
    ]
    svc = _service_with_executions(execs)
    result = await svc.get_strategy_analytics("alpha")
    assert result.average_holding_time_hours == pytest.approx(24.0, rel=0.1)


@pytest.mark.asyncio
async def test_empty_strategy():
    svc = _service_with_executions([])
    result = await svc.get_strategy_analytics("nonexistent")
    assert result.total_signals == 0
    assert result.win_rate == 0.0
    assert result.sharpe_ratio == 0.0


@pytest.mark.asyncio
async def test_get_all_analytics():
    execs = [
        _make_exec("1", "alpha", 0.5, 0.6, pnl=1.0),
        _make_exec("2", "beta", 0.5, 0.7, pnl=2.0),
    ]
    svc = _service_with_executions(execs)
    results = await svc.get_all_analytics()
    assert len(results) == 2
    names = {r.strategy for r in results}
    assert names == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_date_filtering():
    old_ts = "2025-01-01T00:00:00+00:00"
    recent_ts = "2026-06-01T00:00:00+00:00"
    execs = [
        _make_exec("1", "alpha", 0.5, 0.6, pnl=1.0, entry_ts=old_ts),
        _make_exec("2", "alpha", 0.5, 0.7, pnl=2.0, entry_ts=recent_ts),
    ]
    svc = _service_with_executions(execs)
    result = await svc.get_strategy_analytics("alpha", start="2026-01-01T00:00:00+00:00")
    assert result.closed_positions == 1
    assert result.total_signals == 1


@pytest.mark.asyncio
async def test_singleton_instance():
    assert analytics_service is not None
    assert isinstance(analytics_service, ShadowAnalyticsService)
