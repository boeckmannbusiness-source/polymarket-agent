import pytest
from app.services.incubator.strategy_incubator import incubator
from app.schemas.research_memory import CandidateRecommendation
from datetime import datetime, timezone


class TestStrategyIncubator:
    @pytest.mark.asyncio
    async def test_evaluate_approved(self):
        candidate = CandidateRecommendation(
            candidate_id="inc-test-1", strategy_id="inc-test-1",
            archetype="momentum", confidence=0.7, novelty_score=0.6,
            diversity_score=0.5, incubation_ready=True,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        decision = await incubator.evaluate(candidate)
        assert decision.approved is True
        assert decision.to_status == "SHADOW"
        assert len(decision.reasons) >= 1

    @pytest.mark.asyncio
    async def test_evaluate_low_confidence(self):
        candidate = CandidateRecommendation(
            candidate_id="inc-test-2", strategy_id="inc-test-2",
            archetype="momentum", confidence=0.1, novelty_score=0.7,
            diversity_score=0.6, incubation_ready=False,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        decision = await incubator.evaluate(candidate)
        assert decision.approved is False
        assert any("Confidence" in r for r in decision.reasons)

    @pytest.mark.asyncio
    async def test_evaluate_low_novelty(self):
        candidate = CandidateRecommendation(
            candidate_id="inc-test-3", strategy_id="inc-test-3",
            archetype="momentum", confidence=0.6, novelty_score=0.1,
            diversity_score=0.6, incubation_ready=False,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        decision = await incubator.evaluate(candidate)
        assert decision.approved is False
        assert any("Novelty" in r for r in decision.reasons)

    @pytest.mark.asyncio
    async def test_evaluate_low_diversity(self):
        candidate = CandidateRecommendation(
            candidate_id="inc-test-4", strategy_id="inc-test-4",
            archetype="momentum", confidence=0.6, novelty_score=0.6,
            diversity_score=0.1, incubation_ready=False,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        decision = await incubator.evaluate(candidate)
        assert decision.approved is False
        assert any("Diversity" in r for r in decision.reasons)

    @pytest.mark.asyncio
    async def test_evaluate_with_existing_similar(self):
        candidate = CandidateRecommendation(
            candidate_id="inc-test-5", strategy_id="inc-test-5",
            archetype="momentum", confidence=0.6, novelty_score=0.6,
            diversity_score=0.3, incubation_ready=False,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        existing = [
            {"strategy_id": "e1", "archetype": "momentum"},
            {"strategy_id": "e2", "archetype": "momentum"},
            {"strategy_id": "e3", "archetype": "momentum"},
        ]
        decision = await incubator.evaluate(candidate, existing_strategies=existing)
        assert decision.approved is False
        assert any("similar" in r for r in decision.reasons)

    @pytest.mark.asyncio
    async def test_get_decisions(self):
        decisions = await incubator.get_decisions()
        assert isinstance(decisions, list)

    @pytest.mark.asyncio
    async def test_evaluate_default_approved(self):
        candidate = CandidateRecommendation(
            candidate_id="inc-test-6", strategy_id="inc-test-6",
            archetype="novel:ml_sentiment", confidence=0.5, novelty_score=0.5,
            diversity_score=0.5, incubation_ready=True,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        decision = await incubator.evaluate(candidate)
        assert decision.approved is True
