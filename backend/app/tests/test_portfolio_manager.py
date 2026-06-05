import pytest
from app.services.allocation.autonomous_portfolio_manager import portfolio_manager
from app.services.lifecycle.strategy_lifecycle_manager import lifecycle_manager
from app.services.allocation.capital_allocator import capital_allocator


class TestAutonomousPortfolioManager:
    @pytest.mark.asyncio
    async def test_run_review_returns_recommendation(self):
        strategies = [
            {"strategy_id": "pm-s1", "tier": "LIVE", "total_trades": 200, "sharpe": 2.0, "drawdown": 0.05, "confidence": 0.9, "health_score": 90, "rank": 1, "alpha": 0.25, "circuit_breaker_count": 0},
            {"strategy_id": "pm-s2", "tier": "PAPER", "total_trades": 80, "sharpe": 0.9, "drawdown": 0.12, "confidence": 0.6, "health_score": 65, "rank": 2, "alpha": 0.1, "circuit_breaker_count": 0},
        ]
        rec = await portfolio_manager.run_review(strategies)
        assert rec.generated_at
        assert rec.active_strategies is not None
        assert rec.promotion_candidates is not None
        assert rec.retirement_candidates is not None

    @pytest.mark.asyncio
    async def test_run_review_includes_allocation_plan(self):
        strategies = [
            {"strategy_id": "pm-s3", "tier": "LIVE", "total_trades": 150, "sharpe": 1.5, "drawdown": 0.08, "confidence": 0.8, "health_score": 80, "rank": 1, "alpha": 0.15, "circuit_breaker_count": 0},
        ]
        rec = await portfolio_manager.run_review(strategies)
        assert rec.allocation_plan is not None
        assert len(rec.allocation_plan.allocations) > 0

    @pytest.mark.asyncio
    async def test_run_review_handles_disabled_mode(self):
        from app.services.control.control_plane import control_plane
        original = await control_plane.get_execution_mode()
        await control_plane.set_execution_mode("paper")
        rec = await portfolio_manager.run_review([])
        # Should not crash
        assert rec is not None
        await control_plane.set_execution_mode(original)

    @pytest.mark.asyncio
    async def test_get_latest_recommendation(self):
        rec = await portfolio_manager.get_latest_recommendation()
        assert rec is None or isinstance(rec.generated_at, str)

    @pytest.mark.asyncio
    async def test_get_recommendation_history(self):
        history = await portfolio_manager.get_recommendation_history()
        assert isinstance(history, list)

    @pytest.mark.asyncio
    async def test_run_review_excludes_shadow(self):
        strategies = [
            {"strategy_id": "pm-live", "tier": "LIVE", "total_trades": 200, "sharpe": 2.0, "drawdown": 0.05, "confidence": 0.9, "health_score": 90, "rank": 1, "alpha": 0.25, "circuit_breaker_count": 0},
            {"strategy_id": "pm-shadow", "tier": "SHADOW", "total_trades": 50, "sharpe": 1.0, "drawdown": 0.10, "confidence": 0.5, "health_score": 60, "rank": 2, "alpha": 0.05, "circuit_breaker_count": 0},
        ]
        rec = await portfolio_manager.run_review(strategies)
        active_ids = [s["strategy_id"] for s in rec.active_strategies]
        assert "pm-shadow" not in active_ids

    @pytest.mark.asyncio
    async def test_run_review_identifies_retirement_candidates(self):
        strategies = [
            {"strategy_id": "pm-bad", "tier": "LIVE", "total_trades": 5, "sharpe": -0.5, "drawdown": 0.40, "confidence": 0.1, "health_score": 15, "rank": 5, "alpha": -0.3, "circuit_breaker_count": 5},
        ]
        rec = await portfolio_manager.run_review(strategies)
        assert len(rec.retirement_candidates) >= 1
