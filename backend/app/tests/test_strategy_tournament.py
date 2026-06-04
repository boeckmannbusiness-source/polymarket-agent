import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from app.services.shadow.strategy_tournament_service import (
    StrategyTournamentService,
    tournament_service,
)
from app.services.shadow.shadow_execution_service import (
    ShadowExecution,
    shadow_execution_service,
)
from app.schemas.tournament import TournamentRanking


@pytest.fixture(autouse=True)
def _no_redis():
    with patch("app.services.shadow.strategy_tournament_service.StrategyTournamentService._safe_redis", return_value=None):
        with patch("app.services.shadow.shadow_execution_service.ShadowExecutionService._safe_redis", return_value=None):
            with patch("app.services.shadow.shadow_analytics_service.ShadowAnalyticsService._safe_redis", return_value=None):
                with patch("app.services.shadow.shadow_benchmark_service.ShadowBenchmarkService._safe_redis", return_value=None):
                    with patch("app.services.shadow.shadow_promotion_service.ShadowPromotionService._safe_redis", return_value=None):
                        yield


def _make_exec(eid: str, strategy: str, pnl: float | None = None, status: str = "closed") -> ShadowExecution:
    now = datetime.now(timezone.utc).isoformat()
    return ShadowExecution(
        id=eid,
        signal_id=f"sig-{eid}",
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


def _seed_strategies(data: dict[str, list[float]]):
    shadow_execution_service.reset()
    for strategy, pnls in data.items():
        for i, p in enumerate(pnls):
            e = _make_exec(f"{strategy}-{i}", strategy, pnl=p, status="closed")
            shadow_execution_service._executions[e.id] = e


@pytest.mark.asyncio
async def test_rankings_correct_order():
    _seed_strategies({"alpha": [1.0, 2.0, 1.5], "beta": [-1.0, -2.0, -0.5], "gamma": [0.5, 0.3, 0.2]})
    svc = StrategyTournamentService()
    rankings = await svc.get_rankings()
    assert len(rankings) == 3
    assert rankings[0].score >= rankings[1].score >= rankings[2].score


@pytest.mark.asyncio
async def test_rankings_have_valid_percentiles():
    _seed_strategies({"alpha": [1.0, 1.0], "beta": [0.5, 0.5], "gamma": [-0.5, -0.5], "delta": [2.0, 2.0]})
    svc = StrategyTournamentService()
    rankings = await svc.get_rankings()
    for r in rankings:
        assert 0 <= r.percentile <= 100
    assert rankings[0].percentile >= rankings[-1].percentile


@pytest.mark.asyncio
async def test_rankings_have_unique_ranks():
    _seed_strategies({"a": [1.0], "b": [2.0], "c": [3.0], "d": [4.0], "e": [5.0]})
    svc = StrategyTournamentService()
    rankings = await svc.get_rankings()
    ranks = [r.rank for r in rankings]
    assert sorted(ranks) == list(range(1, len(ranks) + 1))


@pytest.mark.asyncio
async def test_rankings_tier_assignment():
    _seed_strategies({"strong": [1.0] * 20, "weak": [-1.0] * 5})
    svc = StrategyTournamentService()
    rankings = await svc.get_rankings()
    tiers = {r.strategy: r.tier for r in rankings}
    assert "strong" in tiers
    assert "weak" in tiers


@pytest.mark.asyncio
async def test_empty_strategies():
    shadow_execution_service.reset()
    svc = StrategyTournamentService()
    rankings = await svc.get_rankings()
    assert rankings == []


@pytest.mark.asyncio
async def test_single_strategy():
    _seed_strategies({"solo": [1.0, 2.0, 3.0]})
    svc = StrategyTournamentService()
    rankings = await svc.get_rankings()
    assert len(rankings) == 1
    assert rankings[0].rank == 1
    assert rankings[0].percentile == 100.0


@pytest.mark.asyncio
async def test_composite_score_deterministic():
    svc = StrategyTournamentService()
    s1 = svc._compute_composite_score(1.5, 1.2, 0.6, 0.05, 0.1, 0.5, 20)
    s2 = svc._compute_composite_score(1.5, 1.2, 0.6, 0.05, 0.1, 0.5, 20)
    assert s1 == s2


@pytest.mark.asyncio
async def test_higher_sharpe_higher_score():
    svc = StrategyTournamentService()
    s_low = svc._compute_composite_score(0.5, 0.3, 0.5, 0.02, 0.2, 0.1, 10)
    s_high = svc._compute_composite_score(2.0, 1.5, 0.7, 0.08, 0.05, 0.8, 30)
    assert s_high > s_low


@pytest.mark.asyncio
async def test_window_metrics():
    _seed_strategies({"alpha": [1.0, 2.0, -0.5]})
    svc = StrategyTournamentService()
    metrics = await svc.get_window_metrics("alpha")
    assert metrics.strategy == "alpha"
    assert metrics.trades_lifetime == 3
    assert metrics.pnl_lifetime != 0.0


@pytest.mark.asyncio
async def test_window_metrics_empty():
    _seed_strategies({"empty": []})
    svc = StrategyTournamentService()
    metrics = await svc.get_window_metrics("empty")
    assert metrics.trades_lifetime == 0
    assert metrics.pnl_lifetime == 0.0


@pytest.mark.asyncio
async def test_all_losing_strategies():
    _seed_strategies({"loser_a": [-1.0, -2.0], "loser_b": [-0.5, -1.5]})
    svc = StrategyTournamentService()
    rankings = await svc.get_rankings()
    assert len(rankings) == 2
    for r in rankings:
        assert r.score >= 0


@pytest.mark.asyncio
async def test_singleton():
    assert tournament_service is not None
    assert isinstance(tournament_service, StrategyTournamentService)
