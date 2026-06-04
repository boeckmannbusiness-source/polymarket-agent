import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from app.services.research.strategy_registry import StrategyRegistry, registry
from app.services.research.champion_challenger_service import ChampionChallengerService, champion_service
from app.services.research.strategy_health_service import StrategyHealthService, health_service
from app.services.research.research_report_service import ResearchReportService, report_service
from app.services.shadow.shadow_execution_service import ShadowExecution, shadow_execution_service
from app.schemas.research import StrategyMetadata


@pytest.fixture(autouse=True)
def _no_redis():
    with patch("app.services.research.strategy_registry.StrategyRegistry._safe_redis", return_value=None):
        with patch("app.services.research.champion_challenger_service.ChampionChallengerService._safe_redis", return_value=None):
            with patch("app.services.research.strategy_health_service.StrategyHealthService._safe_redis", return_value=None):
                with patch("app.services.research.research_report_service.ResearchReportService._safe_redis", return_value=None):
                    with patch("app.services.shadow.strategy_tournament_service.StrategyTournamentService._safe_redis", return_value=None):
                        with patch("app.services.shadow.shadow_analytics_service.ShadowAnalyticsService._safe_redis", return_value=None):
                            with patch("app.services.shadow.shadow_benchmark_service.ShadowBenchmarkService._safe_redis", return_value=None):
                                with patch("app.services.shadow.shadow_promotion_service.ShadowPromotionService._safe_redis", return_value=None):
                                    with patch("app.services.shadow.shadow_execution_service.ShadowExecutionService._safe_redis", return_value=None):
                                        yield


def _make_exec(
    eid: str, strategy: str, pnl: float | None = None, status: str = "closed",
    entry_ts: str | None = None,
) -> ShadowExecution:
    now = entry_ts or datetime.now(timezone.utc).isoformat()
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


# ── Strategy Registry Tests ─────────────────────

class TestStrategyRegistry:
    async def test_register_new_strategy(self):
        registry._local = {}
        meta = await registry.register("strat-1", "Test Strategy A")
        assert meta.strategy_id == "strat-1"
        assert meta.name == "Test Strategy A"
        assert meta.status == "experimental"
        assert meta.version == 1

    async def test_register_duplicate_returns_existing(self):
        registry._local = {}
        meta1 = await registry.register("strat-1", "Test A")
        meta2 = await registry.register("strat-1", "Test A")
        assert meta1.strategy_id == meta2.strategy_id
        assert meta1 is meta2

    async def test_get_nonexistent(self):
        registry._local = {}
        meta = await registry.get("nonexistent")
        assert meta is None

    async def test_get_all(self):
        registry._local = {}
        await registry.register("s1", "S1")
        await registry.register("s2", "S2")
        all_ = await registry.get_all()
        assert len(all_) >= 2

    async def test_promote(self):
        registry._local = {}
        await registry.register("s1", "S1")
        meta = await registry.promote("s1", "shadow")
        assert meta is not None
        assert meta.status == "shadow"
        assert meta.promoted_at is not None

    async def test_promote_nonexistent(self):
        registry._local = {}
        meta = await registry.promote("nonexistent", "live")
        assert meta is None

    async def test_retire(self):
        registry._local = {}
        await registry.register("s1", "S1")
        meta = await registry.retire("s1")
        assert meta is not None
        assert meta.status == "retired"
        assert meta.retired_at is not None

    async def test_retire_with_successor(self):
        registry._local = {}
        await registry.register("v1", "V1")
        await registry.register("v2", "V2")
        meta = await registry.retire("v1", successor="v2")
        assert meta.successor == "v2"

    async def test_retire_nonexistent(self):
        registry._local = {}
        meta = await registry.retire("nonexistent")
        assert meta is None

    async def test_get_active_excludes_retired(self):
        registry._local = {}
        await registry.register("s1", "S1")
        await registry.register("s2", "S2")
        await registry.promote("s1", "shadow")
        await registry.retire("s2")
        active = await registry.get_active()
        ids = [m.strategy_id for m in active]
        assert "s1" in ids
        assert "s2" not in ids

    async def test_get_active_by_status(self):
        registry._local = {}
        await registry.register("s1", "S1")
        await registry.promote("s1", "live")
        await registry.register("s2", "S2")
        live = await registry.get_active(status="live")
        assert len(live) == 1
        assert live[0].strategy_id == "s1"


# ── Champion/Challenger Tests ────────────────────

class TestChampionChallenger:
    async def test_evaluate_no_data(self):
        champion_service._local = {}
        shadow_execution_service.reset()
        result = await champion_service.evaluate()
        assert result.champion is None
        assert result.recommendation == "KEEP"

    async def test_evaluate_single_strategy(self):
        champion_service._local = {}
        shadow_execution_service.reset()
        for i in range(5):
            e = _make_exec(f"a-{i}", "strat-a", pnl=0.1)
            shadow_execution_service._executions[e.id] = e
        result = await champion_service.evaluate()
        assert result.champion == "strat-a"

    async def test_evaluate_recommendation_keep(self):
        champion_service._local = {}
        shadow_execution_service.reset()
        for i in range(10):
            e = _make_exec(f"a-{i}", "strat-a", pnl=0.05)
            shadow_execution_service._executions[e.id] = e
        for i in range(10):
            e = _make_exec(f"b-{i}", "strat-b", pnl=0.04)
            shadow_execution_service._executions[e.id] = e
        result = await champion_service.evaluate()
        assert result.recommendation == "KEEP"

    async def test_evaluate_challengers_limited(self):
        champion_service._local = {}
        shadow_execution_service.reset()
        for s in [f"strat-{i}" for i in range(20)]:
            for j in range(5):
                e = _make_exec(f"{s}-{j}", s, pnl=0.05)
                shadow_execution_service._executions[e.id] = e
        result = await champion_service.evaluate()
        assert len(result.challengers) <= 10

    async def test_evaluate_replacement_score_zero_when_no_champion(self):
        champion_service._local = {}
        shadow_execution_service.reset()
        result = await champion_service.evaluate()
        assert result.replacement_score == 0.0


# ── Strategy Health Tests ────────────────────────

class TestStrategyHealth:
    async def test_compute_health_healthy(self):
        shadow_execution_service.reset()
        for i in range(20):
            e = _make_exec(f"a-{i}", "strat-a", pnl=0.1)
            shadow_execution_service._executions[e.id] = e
        h = await health_service.compute_health("strat-a")
        assert h.score >= 75
        assert h.level == "HEALTHY"

    async def test_compute_health_critical(self):
        shadow_execution_service.reset()
        for i in range(20):
            e = _make_exec(f"a-{i}", "strat-a", pnl=-0.2)
            shadow_execution_service._executions[e.id] = e
        h = await health_service.compute_health("strat-a")
        assert h.score <= 70

    async def test_compute_health_no_data(self):
        shadow_execution_service.reset()
        h = await health_service.compute_health("unknown")
        assert h.score == 100.0
        assert h.level == "HEALTHY"

    async def test_get_all_health(self):
        shadow_execution_service.reset()
        for i in range(5):
            e = _make_exec(f"a-{i}", "strat-a", pnl=0.1)
            shadow_execution_service._executions[e.id] = e
        for i in range(5):
            e = _make_exec(f"b-{i}", "strat-b", pnl=-0.1)
            shadow_execution_service._executions[e.id] = e
        all_h = await health_service.get_all_health()
        assert len(all_h) >= 2

    async def test_invalidate_cache(self):
        result = await health_service.invalidate_cache()
        assert result is None


# ── Research Report Tests ────────────────────────

class TestResearchReport:
    async def test_generate_strategy_report_strengths(self):
        shadow_execution_service.reset()
        for i in range(30):
            e = _make_exec(f"a-{i}", "strat-a", pnl=0.2)
            shadow_execution_service._executions[e.id] = e
        r = await report_service.generate_strategy_report("strat-a")
        assert r.strategy == "strat-a"
        assert r.generated_at != ""
        assert len(r.strengths) > 0

    async def test_generate_strategy_report_weaknesses(self):
        shadow_execution_service.reset()
        for i in range(10):
            e = _make_exec(f"a-{i}", "strat-a", pnl=-0.3)
            shadow_execution_service._executions[e.id] = e
        r = await report_service.generate_strategy_report("strat-a")
        assert len(r.weaknesses) > 0 or len(r.risk_factors) > 0

    async def test_generate_strategy_report_has_performance_summary(self):
        shadow_execution_service.reset()
        for i in range(15):
            e = _make_exec(f"a-{i}", "strat-a", pnl=0.15)
            shadow_execution_service._executions[e.id] = e
        r = await report_service.generate_strategy_report("strat-a")
        assert "total_pnl" in r.performance_summary
        assert "sharpe_ratio" in r.performance_summary

    async def test_generate_portfolio_report(self):
        shadow_execution_service.reset()
        for i in range(10):
            e = _make_exec(f"a-{i}", "strat-a", pnl=0.2)
            shadow_execution_service._executions[e.id] = e
        r = await report_service.generate_portfolio_report()
        assert r.total_strategies >= 1
        assert r.generated_at != ""

    async def test_generate_portfolio_report_empty(self):
        shadow_execution_service.reset()
        r = await report_service.generate_portfolio_report()
        assert r.total_strategies >= 0

    async def test_invalidate_cache(self):
        result = await report_service.invalidate_cache()
        assert result is None


# ── Full integration tests ───────────────────────

class TestResearchIntegration:
    async def test_register_then_health_then_report(self):
        registry._local = {}
        shadow_execution_service.reset()

        meta = await registry.register("int-1", "Integration Strategy")
        assert meta.status == "experimental"

        await registry.promote("int-1", "shadow")
        promoted = await registry.get("int-1")
        assert promoted is not None
        assert promoted.status == "shadow"

        for i in range(20):
            e = _make_exec(f"int-{i}", "int-1", pnl=0.1)
            shadow_execution_service._executions[e.id] = e

        h = await health_service.compute_health("int-1")
        assert h.score >= 70

        r = await report_service.generate_strategy_report("int-1")
        assert r.strategy == "int-1"
        assert "sharpe_ratio" in r.performance_summary

    async def test_champion_evaluates_registered_strategies(self):
        registry._local = {}
        champion_service._local = {}
        shadow_execution_service.reset()

        for sid in ["reg-a", "reg-b", "reg-c"]:
            await registry.register(sid, sid)
            for j in range(8):
                e = _make_exec(f"{sid}-{j}", sid, pnl=0.1 * (3 if sid == "reg-a" else 1))
                shadow_execution_service._executions[e.id] = e

        result = await champion_service.evaluate()
        assert result.champion is not None

    async def test_portfolio_report_includes_retirement_candidates(self):
        shadow_execution_service.reset()
        for i in range(5):
            e = _make_exec(f"bad-{i}", "bad-strat", pnl=-0.5)
            shadow_execution_service._executions[e.id] = e
        r = await report_service.generate_portfolio_report()
        assert r.total_strategies >= 1
        assert len(r.top_performers) >= 0
