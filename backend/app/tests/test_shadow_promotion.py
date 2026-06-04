import pytest
from unittest.mock import patch

from app.services.shadow.shadow_promotion_service import (
    ShadowPromotionService,
    promotion_service,
)
from app.services.shadow.shadow_execution_service import (
    ShadowExecution,
    shadow_execution_service,
)


@pytest.fixture(autouse=True)
def _no_redis():
    with patch("app.services.shadow.shadow_promotion_service.ShadowPromotionService._safe_redis", return_value=None):
        with patch("app.services.shadow.shadow_execution_service.ShadowExecutionService._safe_redis", return_value=None):
            yield


def _make_exec(
    exec_id: str,
    strategy: str,
    pnl: float | None = None,
    status: str = "closed",
) -> ShadowExecution:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    return ShadowExecution(
        id=exec_id,
        signal_id=f"sig-{exec_id}",
        market_id="mkt-1",
        strategy=strategy,
        direction="buy",
        outcome="YES",
        size=10.0,
        entry_price=0.5,
        entry_timestamp=now,
        exit_price=0.5 + (pnl or 0) / 10.0,
        exit_timestamp=now,
        realized_pnl=pnl,
        status=status,
    )


def _seed_strategy(strategy: str, pnls: list[float]):
    shadow_execution_service.reset()
    for i, p in enumerate(pnls):
        e = _make_exec(f"{strategy}-{i}", strategy, pnl=p)
        shadow_execution_service._executions[e.id] = e


def _analytics_for(pnls: list[float]) -> dict:
    wins = sum(1 for p in pnls if p > 0)
    total = len(pnls)
    wr = wins / total if total > 0 else 0.0
    total_pnl = sum(pnls)
    avg = total_pnl / total if total > 0 else 0.0
    import math
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    variance = sum((p - avg) ** 2 for p in pnls) / total if total > 1 else 1
    sharpe = (avg / (math.sqrt(variance) + 0.0001)) * math.sqrt(252) if total > 0 else 0.0
    peak = 0.0
    running = 0.0
    dd = 0.0
    for p in pnls:
        running += p
        if running > peak:
            peak = running
        if peak - running > dd:
            dd = peak - running
    drawdown = dd / (peak + 0.0001) if peak > 0 else 0.0
    return {
        "closed_positions": total,
        "executed_signals": total,
        "win_rate": wr,
        "sharpe_ratio": sharpe,
        "max_drawdown": drawdown,
        "expectancy": avg * (wins / total) - abs(avg) * ((total - wins) / total) if total > 0 else 0.0,
    }


@pytest.mark.asyncio
async def test_eligible_for_live():
    pnls = [1.0, 2.0, 1.5, 0.5, 3.0, 2.0, 1.0, 2.5, 1.8, 0.8, 1.2, 2.2]
    _seed_strategy("alpha", pnls)
    svc = ShadowPromotionService()
    result = await svc.evaluate_strategy("alpha", analytics=_analytics_for(pnls), benchmark={"alpha": 1.0})
    assert result.recommended_tier == "LIVE"
    assert result.confidence_score >= 80


@pytest.mark.asyncio
async def test_eligible_for_paper():
    pnls = [1.0, -0.5, 0.8, -0.3, 0.5, -0.2, 0.3, -0.1, 0.2, 0.1]
    _seed_strategy("beta", pnls)
    svc = ShadowPromotionService()
    result = await svc.evaluate_strategy("beta", analytics=_analytics_for(pnls), benchmark={"alpha": 0.2})
    assert result.recommended_tier in ("PAPER", "LIVE")
    assert len(result.reasons) > 0


@pytest.mark.asyncio
async def test_blocked_by_drawdown():
    pnls = [5.0, -10.0, 3.0, -8.0, 2.0]
    _seed_strategy("gamma", pnls)
    svc = ShadowPromotionService()
    analytics = _analytics_for(pnls)
    result = await svc.evaluate_strategy("gamma", analytics=analytics, benchmark={"alpha": -5.0})
    has_drawdown_blocker = any("Drawdown" in b for b in result.blockers)
    assert has_drawdown_blocker
    assert result.recommended_tier == "SHADOW"


@pytest.mark.asyncio
async def test_blocked_by_insufficient_trades():
    pnls = [1.0]
    _seed_strategy("delta", pnls)
    svc = ShadowPromotionService()
    analytics = _analytics_for(pnls)
    result = await svc.evaluate_strategy("delta", analytics=analytics, benchmark={"alpha": 0.0})
    has_trade_blocker = any("trades" in b for b in result.blockers)
    assert has_trade_blocker
    assert result.recommended_tier == "SHADOW"


@pytest.mark.asyncio
async def test_confidence_score_bounds():
    pnls = [1.0] * 20
    _seed_strategy("epsilon", pnls)
    svc = ShadowPromotionService()
    analytics = _analytics_for(pnls)
    result = await svc.evaluate_strategy("epsilon", analytics=analytics, benchmark={"alpha": 5.0})
    assert 0 <= result.confidence_score <= 100


@pytest.mark.asyncio
async def test_confidence_score_low():
    pnls = [-1.0, -2.0, -3.0]
    _seed_strategy("zeta", pnls)
    svc = ShadowPromotionService()
    analytics = _analytics_for(pnls)
    result = await svc.evaluate_strategy("zeta", analytics=analytics, benchmark={"alpha": -10.0})
    assert result.confidence_score < 50
    assert len(result.blockers) > 0


@pytest.mark.asyncio
async def test_blocked_by_low_sharpe():
    pnls = [1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0]
    _seed_strategy("eta", pnls)
    svc = ShadowPromotionService()
    analytics = _analytics_for(pnls)
    result = await svc.evaluate_strategy("eta", analytics=analytics, benchmark={"alpha": 0.0})
    has_sharpe_blocker = any("Sharpe" in b for b in result.blockers)
    assert has_sharpe_blocker or result.recommended_tier == "SHADOW"


@pytest.mark.asyncio
async def test_blocked_by_low_win_rate():
    pnls = [-1.0, -2.0, -0.5, 3.0, -1.0]
    _seed_strategy("theta", pnls)
    svc = ShadowPromotionService()
    analytics = _analytics_for(pnls)
    result = await svc.evaluate_strategy("theta", analytics=analytics, benchmark={"alpha": -1.0})
    has_wr_blocker = any("Win rate" in b for b in result.blockers)
    assert has_wr_blocker


@pytest.mark.asyncio
async def test_blocked_by_low_expectancy():
    pnls = [0.01, 0.01, -0.02, 0.01, -0.02, 0.01, -0.02, 0.01, -0.02, 0.01]
    _seed_strategy("iota", pnls)
    svc = ShadowPromotionService()
    analytics = _analytics_for(pnls)
    result = await svc.evaluate_strategy("iota", analytics=analytics, benchmark={"alpha": 0.0})
    has_exp_blocker = any("Expectancy" in b for b in result.blockers)
    assert has_exp_blocker or result.recommended_tier == "SHADOW"


@pytest.mark.asyncio
async def test_evaluate_all():
    shadow_execution_service.reset()
    for i in range(5):
        e = _make_exec(f"e{i}", f"strat_{i}", pnl=1.0 if i % 2 == 0 else -1.0)
        shadow_execution_service._executions[e.id] = e
    svc = ShadowPromotionService()
    from unittest.mock import AsyncMock
    svc.evaluate_strategy = AsyncMock(side_effect=svc.evaluate_strategy)
    results = await svc.evaluate_all()
    assert len(results) >= 5


@pytest.mark.asyncio
async def test_promotion_singleton():
    assert promotion_service is not None
    assert isinstance(promotion_service, ShadowPromotionService)
