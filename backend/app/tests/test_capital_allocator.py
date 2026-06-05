import pytest
from app.services.allocation.capital_allocator import capital_allocator
from app.schemas.lifecycle import TierLimits


class TestCapitalAllocator:
    def test_allocate_empty(self):
        plan = capital_allocator.allocate([], mode="balanced")
        assert plan.allocations == []
        assert plan.mode == "balanced"

    def test_allocate_balanced(self):
        strategies = [
            {"strategy_id": "s1", "tier": "LIVE", "sharpe": 2.0, "health_score": 90, "confidence": 0.9, "rank": 1, "total_strategies": 3, "drawdown": 0.05},
            {"strategy_id": "s2", "tier": "LIVE", "sharpe": 1.0, "health_score": 70, "confidence": 0.7, "rank": 2, "total_strategies": 3, "drawdown": 0.10},
            {"strategy_id": "s3", "tier": "PAPER", "sharpe": 0.5, "health_score": 60, "confidence": 0.5, "rank": 3, "total_strategies": 3, "drawdown": 0.15},
        ]
        plan = capital_allocator.allocate(strategies, mode="balanced")
        assert len(plan.allocations) > 0
        assert round(sum(a.allocation_pct for a in plan.allocations), 1) == 100.0

    def test_allocate_conservative(self):
        strategies = [
            {"strategy_id": "s1", "tier": "LIVE", "sharpe": 2.0, "health_score": 90, "confidence": 0.9, "rank": 1, "total_strategies": 2, "drawdown": 0.05},
            {"strategy_id": "s2", "tier": "PAPER", "sharpe": 0.5, "health_score": 60, "confidence": 0.5, "rank": 2, "total_strategies": 2, "drawdown": 0.15},
        ]
        plan = capital_allocator.allocate(strategies, mode="conservative")
        assert round(sum(a.allocation_pct for a in plan.allocations), 1) == 100.0

    def test_allocate_aggressive(self):
        strategies = [
            {"strategy_id": "s1", "tier": "LIVE", "sharpe": 2.5, "health_score": 85, "confidence": 0.85, "rank": 1, "total_strategies": 2, "drawdown": 0.05},
            {"strategy_id": "s2", "tier": "PAPER", "sharpe": 1.8, "health_score": 75, "confidence": 0.75, "rank": 2, "total_strategies": 2, "drawdown": 0.08},
        ]
        plan = capital_allocator.allocate(strategies, mode="aggressive")
        assert round(sum(a.allocation_pct for a in plan.allocations), 1) == 100.0

    def test_allocate_respects_live_cap(self):
        limits = TierLimits(live_max_pct=10.0, paper_max_pct=90.0)
        strategies = [
            {"strategy_id": "s1", "tier": "LIVE", "sharpe": 3.0, "health_score": 95, "confidence": 1.0, "rank": 1, "total_strategies": 2, "drawdown": 0.0},
            {"strategy_id": "s2", "tier": "PAPER", "sharpe": 1.0, "health_score": 70, "confidence": 0.7, "rank": 2, "total_strategies": 2, "drawdown": 0.10},
        ]
        plan = capital_allocator.allocate(strategies, mode="aggressive", limits=limits)
        live_alloc = [a for a in plan.allocations if a.tier == "LIVE"]
        assert len(live_alloc) > 0
        assert live_alloc[0].allocation_pct <= 10.0
        assert round(sum(a.allocation_pct for a in plan.allocations), 1) == 100.0

    def test_shadow_strategies_excluded(self):
        strategies = [
            {"strategy_id": "s1", "tier": "LIVE", "sharpe": 2.0, "health_score": 90, "confidence": 0.9, "rank": 1, "total_strategies": 2, "drawdown": 0.05},
            {"strategy_id": "s2", "tier": "SHADOW", "sharpe": 1.0, "health_score": 70, "confidence": 0.7, "rank": 2, "total_strategies": 2, "drawdown": 0.10},
        ]
        plan = capital_allocator.allocate(strategies, mode="balanced")
        ids = [a.strategy_id for a in plan.allocations]
        assert "s2" not in ids

    def test_min_allocation_floor(self):
        limits = TierLimits(min_allocation_pct=5.0, live_max_pct=95.0)
        strategies = [
            {"strategy_id": "s1", "tier": "LIVE", "sharpe": 0.1, "health_score": 30, "confidence": 0.1, "rank": 1, "total_strategies": 1, "drawdown": 0.20},
        ]
        plan = capital_allocator.allocate(strategies, mode="balanced", limits=limits)
        for a in plan.allocations:
            assert a.allocation_pct >= 5.0

    def test_deterministic_output(self):
        strategies = [
            {"strategy_id": "s1", "tier": "LIVE", "sharpe": 2.0, "health_score": 90, "confidence": 0.9, "rank": 1, "total_strategies": 2, "drawdown": 0.05},
            {"strategy_id": "s2", "tier": "PAPER", "sharpe": 1.0, "health_score": 70, "confidence": 0.7, "rank": 2, "total_strategies": 2, "drawdown": 0.10},
        ]
        plan1 = capital_allocator.allocate(strategies, mode="balanced")
        plan2 = capital_allocator.allocate(strategies, mode="balanced")
        assert [a.allocation_pct for a in plan1.allocations] == [a.allocation_pct for a in plan2.allocations]

    def test_auto_mode_detection(self):
        strategies = [
            {"strategy_id": "s1", "tier": "LIVE", "sharpe": 2.5, "health_score": 95, "confidence": 0.95, "rank": 1, "total_strategies": 2, "drawdown": 0.02},
            {"strategy_id": "s2", "tier": "PAPER", "sharpe": 2.0, "health_score": 85, "confidence": 0.85, "rank": 2, "total_strategies": 2, "drawdown": 0.04},
        ]
        plan = capital_allocator.allocate(strategies, mode="auto")
        assert round(sum(a.allocation_pct for a in plan.allocations), 1) == 100.0
        assert plan.mode in ("balanced", "aggressive", "conservative")

    def test_score_bounds(self):
        strategies = [
            {"strategy_id": "s1", "tier": "LIVE", "sharpe": 0.1, "health_score": 25, "confidence": 0.1, "rank": 10, "total_strategies": 2, "drawdown": 0.40},
        ]
        plan = capital_allocator.allocate(strategies, mode="balanced")
        # Even with poor metrics, should still get allocation (min floor)
        assert len(plan.allocations) > 0
        assert plan.allocations[0].allocation_pct > 0
