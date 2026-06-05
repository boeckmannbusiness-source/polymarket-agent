import pytest
from app.services.governance.strategy_governance import governance
from app.schemas.lifecycle import PromotionRecommendation, RetirementRecommendation, CapitalAllocationPlan, StrategyAllocation
from datetime import datetime, timezone


class TestGovernance:
    def test_explain_promotion(self):
        promo = PromotionRecommendation(
            strategy_id="gov-test-1", current_tier="EXPERIMENTAL",
            recommended_tier="SHADOW", reasons=["Passed all checks", "Score 0.85"],
            score=85.0, source="lifecycle_manager",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        record = governance.explain_promotion(promo)
        assert record.decision_type == "promotion"
        assert "EXPERIMENTAL" in record.reasoning
        assert "SHADOW" in record.reasoning
        assert "Score" in record.reasoning

    def test_explain_retirement(self):
        retire = RetirementRecommendation(
            strategy_id="gov-test-2", reason="Health CRITICAL",
            triggers=["Health CRITICAL (15)", "Drawdown 30.0% > 25%"],
            score=85.0, created_at=datetime.now(timezone.utc).isoformat(),
        )
        record = governance.explain_retirement(retire)
        assert record.decision_type == "retirement"
        assert "CRITICAL" in record.reasoning
        assert "Drawdown" in record.reasoning

    def test_explain_allocation(self):
        plan = CapitalAllocationPlan(
            allocations=[
                StrategyAllocation(strategy_id="s1", tier="LIVE", allocation_pct=60.0, confidence=0.9, health=90, sharpe=2.0, rank=1),
                StrategyAllocation(strategy_id="s2", tier="PAPER", allocation_pct=40.0, confidence=0.7, health=70, sharpe=1.0, rank=2),
            ],
            total_pct=100.0, mode="balanced",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        records = governance.explain_allocation(plan)
        assert len(records) == 2
        assert records[0].decision_type == "allocation"
        assert "60.0%" in records[0].reasoning
        assert "40.0%" in records[1].reasoning

    @pytest.mark.asyncio
    async def test_persist_and_get_records(self):
        promo = PromotionRecommendation(
            strategy_id="gov-persist", current_tier="SHADOW",
            recommended_tier="PAPER", reasons=["Test"], score=70.0,
            source="test", created_at=datetime.now(timezone.utc).isoformat(),
        )
        record = governance.explain_promotion(promo)
        await governance.persist(record)
        records = await governance.get_records()
        assert len(records) >= 1
        found = any(r.record_id == record.record_id for r in records)
        assert found

    @pytest.mark.asyncio
    async def test_get_promotion_records(self):
        promo_records = await governance.get_promotion_records()
        assert isinstance(promo_records, list)

    @pytest.mark.asyncio
    async def test_get_retirement_records(self):
        retire_records = await governance.get_retirement_records()
        assert isinstance(retire_records, list)

    @pytest.mark.asyncio
    async def test_get_allocation_records(self):
        alloc_records = await governance.get_allocation_records()
        assert isinstance(alloc_records, list)

    def test_explain_promotion_with_details(self):
        promo = PromotionRecommendation(
            strategy_id="gov-details", current_tier="PAPER",
            recommended_tier="LIVE", reasons=["Rank #1"], score=95.0,
            source="test", created_at=datetime.now(timezone.utc).isoformat(),
        )
        record = governance.explain_promotion(promo, details={"total_strategies": 10, "trades": 200})
        assert record.details["total_strategies"] == 10
        assert record.details["trades"] == 200

    def test_explain_allocation_deterministic(self):
        plan = CapitalAllocationPlan(
            allocations=[
                StrategyAllocation(strategy_id="s1", tier="LIVE", allocation_pct=50.0, confidence=0.8, health=80, sharpe=1.5, rank=1),
            ],
            total_pct=50.0, mode="balanced",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        r1 = governance.explain_allocation(plan)
        r2 = governance.explain_allocation(plan)
        assert len(r1) == len(r2)
        for a, b in zip(r1, r2):
            assert a.reasoning == b.reasoning
            assert a.details == b.details
