import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from app.services.shadow.allocation_engine import AllocationEngine, allocation_engine
from app.services.shadow.shadow_execution_service import (
    ShadowExecution,
    shadow_execution_service,
)
from app.schemas.shadow import PromotionThresholds
from app.services.shadow.shadow_promotion_service import promotion_service


@pytest.fixture(autouse=True)
def _no_redis():
    with patch("app.services.shadow.allocation_engine.AllocationEngine._safe_redis", return_value=None):
        with patch("app.services.shadow.shadow_execution_service.ShadowExecutionService._safe_redis", return_value=None):
            with patch("app.services.shadow.shadow_analytics_service.ShadowAnalyticsService._safe_redis", return_value=None):
                with patch("app.services.shadow.shadow_benchmark_service.ShadowBenchmarkService._safe_redis", return_value=None):
                    with patch("app.services.shadow.shadow_promotion_service.ShadowPromotionService._safe_redis", return_value=None):
                        with patch("app.services.shadow.strategy_tournament_service.StrategyTournamentService._safe_redis", return_value=None):
                            yield


def _make_exec(eid: str, strategy: str, pnl: float | None = 0.0, status: str = "closed") -> ShadowExecution:
    now = datetime.now(timezone.utc).isoformat()
    return ShadowExecution(
        id=eid, signal_id=f"sig-{eid}", market_id="mkt-1", strategy=strategy,
        direction="buy", outcome="YES", size=10.0, entry_price=0.5,
        entry_timestamp=now, exit_price=0.5, exit_timestamp=now,
        realized_pnl=pnl, status=status,
    )


def _seed(strategies: list[str]):
    shadow_execution_service.reset()
    for s in strategies:
        for i in range(3):
            e = _make_exec(f"{s}-{i}", s, pnl=1.0 if s != "loser" else -1.0)
            shadow_execution_service._executions[e.id] = e


@pytest.mark.asyncio
async def test_equal_weight_sums_to_100():
    _seed(["a", "b", "c", "d"])
    result = await allocation_engine.compute_allocation(mode="equal", total_capital=100000)
    total = sum(a.allocation_pct for a in result.allocations)
    assert total == pytest.approx(100.0, rel=0.01)


@pytest.mark.asyncio
async def test_equal_weight_assignments():
    _seed(["x", "y"])
    result = await allocation_engine.compute_allocation(mode="equal", total_capital=100000)
    for a in result.allocations:
        assert a.allocation_pct == 50.0
        assert a.capital_assigned == 50000.0


@pytest.mark.asyncio
async def test_sharpe_weight_sums_to_100():
    _seed(["alpha", "beta", "gamma"])
    result = await allocation_engine.compute_allocation(mode="sharpe", total_capital=100000)
    total = sum(a.allocation_pct for a in result.allocations)
    assert total == pytest.approx(100.0, rel=0.01)


@pytest.mark.asyncio
async def test_risk_parity_sums_to_100():
    _seed(["a", "b"])
    result = await allocation_engine.compute_allocation(mode="risk_parity", total_capital=100000)
    total = sum(a.allocation_pct for a in result.allocations)
    assert total == pytest.approx(100.0, rel=0.01)


@pytest.mark.asyncio
async def test_confidence_weight_sums_to_100():
    _seed(["a", "b"])
    result = await allocation_engine.compute_allocation(mode="confidence", total_capital=100000)
    total = sum(a.allocation_pct for a in result.allocations)
    assert total == pytest.approx(100.0, rel=0.01)


@pytest.mark.asyncio
async def test_hybrid_weight_sums_to_100():
    _seed(["a", "b", "c"])
    result = await allocation_engine.compute_allocation(mode="hybrid", total_capital=100000)
    total = sum(a.allocation_pct for a in result.allocations)
    assert total == pytest.approx(100.0, rel=0.01)


@pytest.mark.asyncio
async def test_all_modes_return_five():
    _seed(["a", "b"])
    results = await allocation_engine.get_all_modes(total_capital=100000)
    assert len(results) == 5
    modes = {r.mode for r in results}
    assert modes == {"equal", "sharpe", "risk_parity", "confidence", "hybrid"}


@pytest.mark.asyncio
async def test_single_strategy_gets_100_percent():
    _seed(["solo"])
    result = await allocation_engine.compute_allocation(mode="equal", total_capital=50000)
    assert len(result.allocations) == 1
    assert result.allocations[0].allocation_pct == 100.0
    assert result.allocations[0].capital_assigned == 50000.0


@pytest.mark.asyncio
async def test_empty_strategies():
    shadow_execution_service.reset()
    result = await allocation_engine.compute_allocation(mode="equal", total_capital=100000)
    assert result.allocations == []


@pytest.mark.asyncio
async def test_capital_respected():
    _seed(["a", "b", "c"])
    result = await allocation_engine.compute_allocation(mode="equal", total_capital=77777)
    total_cap = sum(a.capital_assigned for a in result.allocations)
    assert total_cap == pytest.approx(77777.0, rel=0.01)


@pytest.mark.asyncio
async def test_risk_score_bounds():
    _seed(["a", "b"])
    result = await allocation_engine.compute_allocation(mode="equal", total_capital=100000)
    for a in result.allocations:
        assert 0 <= a.risk_score <= 1.0


@pytest.mark.asyncio
async def test_unknown_mode_falls_back_to_equal():
    _seed(["a", "b"])
    result = await allocation_engine.compute_allocation(mode="unknown", total_capital=100000)
    for a in result.allocations:
        assert a.allocation_pct == 50.0


@pytest.mark.asyncio
async def test_singleton():
    assert allocation_engine is not None
    assert isinstance(allocation_engine, AllocationEngine)
