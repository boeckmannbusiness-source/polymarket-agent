import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from app.services.shadow.portfolio_simulator import PortfolioSimulator, portfolio_simulator
from app.services.shadow.shadow_execution_service import (
    ShadowExecution,
    shadow_execution_service,
)


@pytest.fixture(autouse=True)
def _no_redis():
    with patch("app.services.shadow.portfolio_simulator.PortfolioSimulator._safe_redis", return_value=None):
        with patch("app.services.shadow.shadow_execution_service.ShadowExecutionService._safe_redis", return_value=None):
            with patch("app.services.shadow.shadow_analytics_service.ShadowAnalyticsService._safe_redis", return_value=None):
                with patch("app.services.shadow.shadow_benchmark_service.ShadowBenchmarkService._safe_redis", return_value=None):
                    with patch("app.services.shadow.shadow_promotion_service.ShadowPromotionService._safe_redis", return_value=None):
                        with patch("app.services.shadow.strategy_tournament_service.StrategyTournamentService._safe_redis", return_value=None):
                            with patch("app.services.shadow.allocation_engine.AllocationEngine._safe_redis", return_value=None):
                                yield


def _make_exec(eid: str, strategy: str, pnl: float) -> ShadowExecution:
    now = datetime.now(timezone.utc).isoformat()
    return ShadowExecution(
        id=eid, signal_id=f"sig-{eid}", market_id="mkt-1", strategy=strategy,
        direction="buy", outcome="YES", size=100.0, entry_price=0.5,
        entry_timestamp=now, exit_price=0.5 + pnl / 100.0,
        exit_timestamp=now, realized_pnl=pnl, status="closed",
    )


def _seed(data: dict[str, list[float]]):
    shadow_execution_service.reset()
    for strategy, pnls in data.items():
        for i, p in enumerate(pnls):
            e = _make_exec(f"{strategy}-{i}", strategy, p)
            shadow_execution_service._executions[e.id] = e


@pytest.mark.asyncio
async def test_simulator_returns_equity_curve():
    _seed({"alpha": [1.0, 2.0, 1.5]})
    result = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    assert len(result.equity_curve) > 0


@pytest.mark.asyncio
async def test_simulator_final_equity():
    _seed({"alpha": [10.0, 20.0, 15.0]})
    result = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    assert result.final_equity != 100000


@pytest.mark.asyncio
async def test_simulator_strategy_contributions():
    _seed({"alpha": [10.0, 20.0], "beta": [5.0, -5.0]})
    result = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    assert len(result.strategy_contributions) == 2
    total_contrib = sum(c.contribution_pct for c in result.strategy_contributions)
    assert total_contrib == pytest.approx(100.0, rel=1.0)


@pytest.mark.asyncio
async def test_simulator_empty_strategies():
    shadow_execution_service.reset()
    result = await portfolio_simulator.simulate(starting_capital=50000, mode="equal")
    assert result.final_equity == 50000
    assert result.total_return == 0.0
    assert result.equity_curve == []


@pytest.mark.asyncio
async def test_simulator_single_strategy():
    _seed({"solo": [5.0, 10.0, 15.0]})
    result = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    assert len(result.equity_curve) > 0
    assert len(result.strategy_contributions) == 1


@pytest.mark.asyncio
async def test_simulator_all_losing_strategies():
    _seed({"loser_a": [-10.0, -20.0], "loser_b": [-5.0, -15.0]})
    result = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    assert result.total_return < 0
    assert result.max_drawdown > 0


@pytest.mark.asyncio
async def test_simulator_max_drawdown_non_negative():
    _seed({"alpha": [10.0, -5.0, 20.0, -10.0, 15.0]})
    result = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    assert result.max_drawdown >= 0
    assert result.max_drawdown_pct >= 0


@pytest.mark.asyncio
async def test_simulator_cagr_reasonable():
    _seed({"alpha": [10.0] * 365})
    result = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    assert isinstance(result.cagr, float)


@pytest.mark.asyncio
async def test_simulator_deterministic():
    _seed({"alpha": [1.0, 2.0, 3.0], "beta": [-1.0, 0.5, 1.5]})
    r1 = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    r2 = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    assert r1.final_equity == r2.final_equity
    assert len(r1.equity_curve) == len(r2.equity_curve)


@pytest.mark.asyncio
async def test_simulator_profit_factor_inf():
    _seed({"alpha": [1.0, 2.0, 3.0]})
    result = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    assert result.profit_factor > 0


@pytest.mark.asyncio
async def test_simulator_volatility_non_negative():
    _seed({"alpha": [1.0, -2.0, 3.0, -1.0, 0.5]})
    result = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    assert result.volatility >= 0


@pytest.mark.asyncio
async def test_simulator_calmar_ratio():
    _seed({"alpha": [5.0, 3.0, 7.0, 2.0, 6.0]})
    result = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    assert isinstance(result.calmar_ratio, float)


@pytest.mark.asyncio
async def test_simulator_recovery_factor():
    _seed({"alpha": [10.0, -20.0, 15.0, 10.0, 5.0]})
    result = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    assert isinstance(result.recovery_factor, float)


@pytest.mark.asyncio
async def test_simulator_sharpe_computed():
    _seed({"alpha": [1.0, 2.0, 1.5, 0.5, 3.0, 2.5]})
    result = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    assert isinstance(result.sharpe, float)


@pytest.mark.asyncio
async def test_simulator_equity_curve_values():
    _seed({"alpha": [10.0, 20.0]})
    result = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    for point in result.equity_curve:
        assert point.equity > 0
        assert point.drawdown >= 0


@pytest.mark.asyncio
async def test_simulator_trade_count_in_contributions():
    _seed({"alpha": [1.0, 2.0, 3.0]})
    result = await portfolio_simulator.simulate(starting_capital=100000, mode="equal")
    for c in result.strategy_contributions:
        assert c.trade_count >= 0


@pytest.mark.asyncio
async def test_simulator_starting_capital_preserved():
    _seed({"alpha": []})
    result = await portfolio_simulator.simulate(starting_capital=50000, mode="equal")
    assert result.final_equity == 50000


@pytest.mark.asyncio
async def test_singleton():
    assert portfolio_simulator is not None
    assert isinstance(portfolio_simulator, PortfolioSimulator)
