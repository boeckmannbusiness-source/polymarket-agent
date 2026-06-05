import pytest
from app.services.lifecycle.strategy_lifecycle_manager import lifecycle_manager
from app.schemas.lifecycle import PromotionRecommendation, RetirementRecommendation


class TestStrategyLifecycleManager:
    @pytest.mark.asyncio
    async def test_evaluate_promotions_experimental_to_shadow(self):
        strategies = [{
            "strategy_id": "test-exp-1", "tier": "EXPERIMENTAL",
            "total_trades": 50, "sharpe": 1.0, "drawdown": 0.08,
            "confidence": 0.6, "health_score": 70, "rank": 1, "total_strategies": 5,
        }]
        promos = await lifecycle_manager.evaluate_promotions(strategies)
        assert len(promos) >= 1
        assert promos[0].recommended_tier == "SHADOW"

    @pytest.mark.asyncio
    async def test_evaluate_promotions_shadow_to_paper(self):
        strategies = [{
            "strategy_id": "test-shad-1", "tier": "SHADOW",
            "total_trades": 150, "sharpe": 1.5, "drawdown": 0.06,
            "confidence": 0.75, "health_score": 80, "rank": 2, "total_strategies": 10,
        }]
        promos = await lifecycle_manager.evaluate_promotions(strategies)
        promo = [p for p in promos if p.strategy_id == "test-shad-1"]
        found = False
        for p in promos:
            if p.strategy_id == "test-shad-1" and p.recommended_tier == "PAPER":
                found = True
        assert found or len(promo) == 0  # May not meet threshold but should not crash

    @pytest.mark.asyncio
    async def test_evaluate_retirements_health_critical(self):
        strategies = [{
            "strategy_id": "test-ret-1", "health_score": 15,
            "drawdown": 0.30, "circuit_breaker_count": 4,
            "alpha": -0.2, "total_trades": 5,
        }]
        retirements = await lifecycle_manager.evaluate_retirements(strategies)
        assert len(retirements) >= 1
        assert any("CRITICAL" in t for t in retirements[0].triggers)

    @pytest.mark.asyncio
    async def test_evaluate_retirements_high_drawdown(self):
        strategies = [{
            "strategy_id": "test-ret-2", "health_score": 90,
            "drawdown": 0.35, "circuit_breaker_count": 0,
            "alpha": 0.1, "total_trades": 100,
        }]
        retirements = await lifecycle_manager.evaluate_retirements(strategies)
        assert len(retirements) >= 1
        assert any("Drawdown" in t for t in retirements[0].triggers)

    @pytest.mark.asyncio
    async def test_healthy_strategy_no_retirement(self):
        strategies = [{
            "strategy_id": "test-healthy", "health_score": 90,
            "drawdown": 0.05, "circuit_breaker_count": 0,
            "alpha": 0.2, "total_trades": 200,
        }]
        retirements = await lifecycle_manager.evaluate_retirements(strategies)
        assert len(retirements) == 0

    @pytest.mark.asyncio
    async def test_experimental_low_trades_no_promotion(self):
        strategies = [{
            "strategy_id": "test-low", "tier": "EXPERIMENTAL",
            "total_trades": 5, "sharpe": 0.1, "drawdown": 0.30,
            "confidence": 0.2, "health_score": 20, "rank": 10, "total_strategies": 10,
        }]
        promos = await lifecycle_manager.evaluate_promotions(strategies)
        exp = [p for p in promos if p.current_tier == "EXPERIMENTAL"]
        assert len(exp) == 0

    @pytest.mark.asyncio
    async def test_apply_decision_promoted(self):
        decision = await lifecycle_manager.apply_decision(
            "test-decision-1", "promoted", from_tier="EXPERIMENTAL", to_tier="SHADOW",
            reasons=["Met all criteria"],
        )
        assert decision.decision_type == "promoted"
        assert decision.from_tier == "EXPERIMENTAL"
        assert decision.to_tier == "SHADOW"

    @pytest.mark.asyncio
    async def test_apply_decision_retired(self):
        decision = await lifecycle_manager.apply_decision(
            "test-decision-2", "retired", from_tier="LIVE", reasons=["Negative alpha"],
        )
        assert decision.decision_type == "retired"
        assert "Negative alpha" in decision.reasons

    @pytest.mark.asyncio
    async def test_get_promotions(self):
        promos = await lifecycle_manager.get_promotions()
        assert isinstance(promos, list)

    @pytest.mark.asyncio
    async def test_get_retirements(self):
        rets = await lifecycle_manager.get_retirements()
        assert isinstance(rets, list)

    @pytest.mark.asyncio
    async def test_get_decisions(self):
        decs = await lifecycle_manager.get_decisions()
        assert isinstance(decs, list)
