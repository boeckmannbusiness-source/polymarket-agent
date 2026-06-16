import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.shadow.shadow_execution_service import (
    ShadowExecutionService,
    ShadowExecution,
    shadow_execution_service,
)


@pytest.fixture(autouse=True)
def _no_redis():
    with patch("app.services.shadow.shadow_execution_service.ShadowExecutionService._safe_redis", return_value=None):
        yield


def _fresh_service() -> ShadowExecutionService:
    svc = ShadowExecutionService()
    svc.reset()
    return svc


@pytest.mark.asyncio
async def test_create_execution():
    service = _fresh_service()
    exec_ = await service.create_execution(
        signal_id="sig-1",
        market_id="mkt-1",
        strategy="test_strat",
        direction="buy",
        outcome="YES",
        size=50.0,
        entry_price=0.55,
        signal_confidence=0.8,
    )
    assert exec_.id is not None
    assert exec_.signal_id == "sig-1"
    assert exec_.market_id == "mkt-1"
    assert exec_.strategy == "test_strat"
    assert exec_.direction == "buy"
    assert exec_.outcome == "YES"
    assert exec_.size == 50.0
    assert exec_.entry_price == 0.55
    assert exec_.signal_confidence == 0.8
    assert exec_.status == "open"
    assert exec_.realized_pnl is None


@pytest.mark.asyncio
async def test_create_execution_is_stored():
    service = _fresh_service()
    exec_ = await service.create_execution(
        signal_id="sig-1", market_id="mkt-1", strategy="s",
        direction="buy", outcome="YES", size=10, entry_price=0.5,
    )
    retrieved = service.get_execution(exec_.id)
    assert retrieved is not None
    assert retrieved.id == exec_.id


@pytest.mark.asyncio
async def test_get_all_executions():
    service = _fresh_service()
    await service.create_execution(
        signal_id="s1", market_id="m1", strategy="s",
        direction="buy", outcome="YES", size=10, entry_price=0.5,
    )
    await service.create_execution(
        signal_id="s2", market_id="m2", strategy="s",
        direction="sell", outcome="NO", size=20, entry_price=0.6,
    )
    all_execs = service.get_all_executions()
    assert len(all_execs) == 2


@pytest.mark.asyncio
async def test_get_open_and_closed():
    service = _fresh_service()
    e1 = await service.create_execution(
        signal_id="s1", market_id="m1", strategy="s",
        direction="buy", outcome="YES", size=10, entry_price=0.5,
    )
    e2 = await service.create_execution(
        signal_id="s2", market_id="m2", strategy="s",
        direction="sell", outcome="NO", size=20, entry_price=0.6,
    )
    await service.close_execution(e1.id, exit_price=0.7)
    open_execs = service.get_open_executions()
    closed_execs = service.get_closed_executions()
    assert len(open_execs) == 1
    assert len(closed_execs) == 1
    assert open_execs[0].id == e2.id
    assert closed_execs[0].id == e1.id


@pytest.mark.asyncio
async def test_update_current_price_unrealized_pnl_buy():
    service = _fresh_service()
    exec_ = await service.create_execution(
        signal_id="s1", market_id="m1", strategy="s",
        direction="buy", outcome="YES", size=10, entry_price=0.5,
    )
    await service.update_current_price(exec_.id, 0.7)
    updated = service.get_execution(exec_.id)
    assert updated is not None
    assert updated.current_price == 0.7
    assert updated.unrealized_pnl == pytest.approx(4.0)


@pytest.mark.asyncio
async def test_update_current_price_unrealized_pnl_sell():
    service = _fresh_service()
    exec_ = await service.create_execution(
        signal_id="s1", market_id="m1", strategy="s",
        direction="sell", outcome="NO", size=10, entry_price=0.5,
    )
    await service.update_current_price(exec_.id, 0.3)
    updated = service.get_execution(exec_.id)
    assert updated is not None
    assert updated.current_price == 0.3
    assert updated.unrealized_pnl == pytest.approx(4.0)


@pytest.mark.asyncio
async def test_close_execution_buy():
    service = _fresh_service()
    exec_ = await service.create_execution(
        signal_id="s1", market_id="m1", strategy="s",
        direction="buy", outcome="YES", size=10, entry_price=0.5,
    )
    await service.close_execution(exec_.id, exit_price=0.8)
    closed = service.get_execution(exec_.id)
    assert closed is not None
    assert closed.status == "closed"
    assert closed.exit_price == 0.8
    assert closed.outcome_resolved is True
    assert closed.realized_pnl == pytest.approx(6.0)
    assert closed.unrealized_pnl == 0.0


@pytest.mark.asyncio
async def test_close_execution_sell():
    service = _fresh_service()
    exec_ = await service.create_execution(
        signal_id="s1", market_id="m1", strategy="s",
        direction="sell", outcome="NO", size=10, entry_price=0.6,
    )
    await service.close_execution(exec_.id, exit_price=0.2)
    closed = service.get_execution(exec_.id)
    assert closed is not None
    assert closed.realized_pnl == pytest.approx(6.66666666)


@pytest.mark.asyncio
async def test_close_already_closed_returns_none():
    service = _fresh_service()
    exec_ = await service.create_execution(
        signal_id="s1", market_id="m1", strategy="s",
        direction="buy", outcome="YES", size=10, entry_price=0.5,
    )
    await service.close_execution(exec_.id, exit_price=0.8)
    result = await service.close_execution(exec_.id, exit_price=0.9)
    assert result is None


@pytest.mark.asyncio
async def test_update_nonexistent_execution():
    service = _fresh_service()
    result = await service.update_current_price("nonexistent", 0.5)
    assert result is None


@pytest.mark.asyncio
async def test_close_nonexistent_execution():
    service = _fresh_service()
    result = await service.close_execution("nonexistent", 0.5)
    assert result is None


@pytest.mark.asyncio
async def test_get_executions_by_strategy():
    service = _fresh_service()
    await service.create_execution(
        signal_id="s1", market_id="m1", strategy="alpha",
        direction="buy", outcome="YES", size=10, entry_price=0.5,
    )
    await service.create_execution(
        signal_id="s2", market_id="m2", strategy="beta",
        direction="sell", outcome="NO", size=20, entry_price=0.6,
    )
    await service.create_execution(
        signal_id="s3", market_id="m3", strategy="alpha",
        direction="buy", outcome="YES", size=15, entry_price=0.55,
    )
    alpha_execs = service.get_executions_by_strategy("alpha")
    assert len(alpha_execs) == 2
    beta_execs = service.get_executions_by_strategy("beta")
    assert len(beta_execs) == 1


@pytest.mark.asyncio
async def test_get_executions_by_market():
    service = _fresh_service()
    await service.create_execution(
        signal_id="s1", market_id="m1", strategy="s",
        direction="buy", outcome="YES", size=10, entry_price=0.5,
    )
    await service.create_execution(
        signal_id="s2", market_id="m2", strategy="s",
        direction="sell", outcome="NO", size=20, entry_price=0.6,
    )
    await service.create_execution(
        signal_id="s3", market_id="m1", strategy="s",
        direction="buy", outcome="YES", size=15, entry_price=0.55,
    )
    m1_execs = service.get_executions_by_market("m1")
    assert len(m1_execs) == 2
    m2_execs = service.get_executions_by_market("m2")
    assert len(m2_execs) == 1


@pytest.mark.asyncio
async def test_process_signal():
    service = _fresh_service()
    signal = {
        "id": "sig-1",
        "market_id": "mkt-1",
        "signal_type": "momentum",
        "direction": "buy",
        "confidence": 0.85,
        "estimated_probability": 0.62,
        "implied_probability": None,
        "source_agent": "agent_alpha",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    exec_ = await service.process_signal(signal)
    assert exec_ is not None
    assert exec_.signal_id == "sig-1"
    assert exec_.market_id == "mkt-1"
    assert exec_.strategy == "agent_alpha"
    assert exec_.direction == "buy"
    assert exec_.size == 85.0
    assert exec_.entry_price == 0.62


@pytest.mark.asyncio
async def test_process_signal_uses_signal_type_as_strategy_fallback():
    service = _fresh_service()
    signal = {
        "id": "sig-2",
        "market_id": "mkt-2",
        "signal_type": "mean_reversion",
        "direction": "sell",
        "confidence": 0.5,
        "estimated_probability": None,
        "implied_probability": 0.48,
        "source_agent": None,
    }
    exec_ = await service.process_signal(signal)
    assert exec_.strategy == "mean_reversion"
    assert exec_.entry_price == 0.48


@pytest.mark.asyncio
async def test_get_strategy_performance():
    service = _fresh_service()
    await service.create_execution(
        signal_id="s1", market_id="m1", strategy="alpha",
        direction="buy", outcome="YES", size=10, entry_price=0.5,
    )
    e2 = await service.create_execution(
        signal_id="s2", market_id="m2", strategy="alpha",
        direction="buy", outcome="YES", size=10, entry_price=0.5,
    )
    await service.close_execution(e2.id, exit_price=0.8)
    perf = service.get_strategy_performance("alpha")
    assert perf["strategy"] == "alpha"
    assert perf["total_executions"] == 2
    assert perf["closed_executions"] == 1
    assert perf["open_executions"] == 1
    assert perf["total_realized_pnl"] == pytest.approx(6.0)
    assert perf["win_count"] == 1
    assert perf["loss_count"] == 0
    assert perf["win_rate"] == 1.0


@pytest.mark.asyncio
async def test_get_all_strategy_performance():
    service = _fresh_service()
    await service.create_execution(
        signal_id="s1", market_id="m1", strategy="alpha",
        direction="buy", outcome="YES", size=10, entry_price=0.5,
    )
    await service.create_execution(
        signal_id="s2", market_id="m2", strategy="beta",
        direction="sell", outcome="NO", size=20, entry_price=0.6,
    )
    all_perf = service.get_all_strategy_performance()
    assert len(all_perf) == 2
    strat_names = {p["strategy"] for p in all_perf}
    assert strat_names == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_get_overall_performance():
    service = _fresh_service()
    await service.create_execution(
        signal_id="s1", market_id="m1", strategy="alpha",
        direction="buy", outcome="YES", size=10, entry_price=0.5,
    )
    e2 = await service.create_execution(
        signal_id="s2", market_id="m2", strategy="beta",
        direction="sell", outcome="NO", size=20, entry_price=0.6,
    )
    await service.close_execution(e2.id, exit_price=0.3)
    overall = service.get_overall_performance()
    assert overall["total_executions"] == 2
    assert overall["closed_executions"] == 1
    assert overall["open_executions"] == 1
    assert overall["total_realized_pnl"] == pytest.approx(10.0)
    assert overall["strategy_count"] == 2
    assert overall["win_count"] == 1
    assert overall["loss_count"] == 0


@pytest.mark.asyncio
async def test_reset():
    service = _fresh_service()
    assert len(service.get_all_executions()) == 0
    await service.create_execution(
        signal_id="s1", market_id="m1", strategy="s",
        direction="buy", outcome="YES", size=10, entry_price=0.5,
    )
    assert len(service.get_all_executions()) == 1
    service.reset()
    assert len(service.get_all_executions()) == 0


@pytest.mark.asyncio
async def test_sync_from_signals_no_db():
    service = _fresh_service()
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = []
    report = await service.sync_from_signals(db)
    assert report["created"] == 0
    assert report["skipped"] == 0


@pytest.mark.asyncio
async def test_singleton_instance():
    assert shadow_execution_service is not None
    assert isinstance(shadow_execution_service, ShadowExecutionService)


@pytest.mark.asyncio
async def test_refresh_prices_no_open_executions():
    service = _fresh_service()
    db = AsyncMock()
    result = await service.refresh_prices(db)
    assert result["updated"] == 0


@pytest.mark.asyncio
async def test_strategy_performance_no_trades():
    service = _fresh_service()
    perf = service.get_strategy_performance("nonexistent")
    assert perf["total_executions"] == 0
    assert perf["win_rate"] == 0.0
    assert perf["sharpe"] == 0.0


@pytest.mark.asyncio
async def test_overall_performance_no_trades():
    service = _fresh_service()
    overall = service.get_overall_performance()
    assert overall["total_executions"] == 0
    assert overall["win_rate"] == 0.0
    assert overall["sharpe"] == 0.0


@pytest.mark.asyncio
async def test_close_execution_sets_unrealized_to_zero():
    service = _fresh_service()
    exec_ = await service.create_execution(
        signal_id="s1", market_id="m1", strategy="s",
        direction="buy", outcome="YES", size=10, entry_price=0.5,
    )
    await service.update_current_price(exec_.id, 0.7)
    await service.close_execution(exec_.id, exit_price=0.8)
    closed = service.get_execution(exec_.id)
    assert closed.unrealized_pnl == 0.0


@pytest.mark.asyncio
async def test_safe_redis_returns_none_when_unavailable():
    service = _fresh_service()
    result = await service._safe_redis()
    assert result is None
