import pytest

from app.services.research.signal_scoring_service import SignalScoringService, scoring_service
from app.schemas.signals import SignalScore


class TestSignalScoringService:
    async def test_high_confidence_high_evidence(self):
        score = await scoring_service.compute_score(
            signal_id="sig-1",
            confidence_score=90.0,
            evidence_score=85.0,
            novelty_score=70.0,
            historical_accuracy_score=80.0,
        )
        assert 0 <= score.composite_score <= 100
        assert score.composite_score > 50

    async def test_low_scores(self):
        score = await scoring_service.compute_score(
            signal_id="sig-2",
            confidence_score=10.0,
            evidence_score=5.0,
            novelty_score=5.0,
            historical_accuracy_score=0.0,
        )
        assert score.composite_score < 20

    async def test_composite_formula(self):
        score = await scoring_service.compute_score(
            signal_id="sig-3",
            confidence_score=100.0,
            evidence_score=100.0,
            novelty_score=100.0,
            historical_accuracy_score=100.0,
        )
        assert score.composite_score == 100.0

    async def test_weight_distribution(self):
        score1 = await scoring_service.compute_score("s1", confidence_score=100, evidence_score=0, novelty_score=0, historical_accuracy_score=0)
        score2 = await scoring_service.compute_score("s2", confidence_score=0, evidence_score=100, novelty_score=0, historical_accuracy_score=0)
        assert score1.composite_score > score2.composite_score  # confidence 40% > evidence 30%

    async def test_clamps_above_100(self):
        score = await scoring_service.compute_score("s1", confidence_score=200, evidence_score=200, novelty_score=200, historical_accuracy_score=200)
        assert score.composite_score <= 100
        assert score.confidence_score <= 100

    async def test_clamps_below_0(self):
        score = await scoring_service.compute_score("s1", confidence_score=-50, evidence_score=-50, novelty_score=-50, historical_accuracy_score=-50)
        assert score.composite_score >= 0
        assert score.confidence_score >= 0

    async def test_zero_scores(self):
        score = await scoring_service.compute_score("s1", confidence_score=0, evidence_score=0, novelty_score=0, historical_accuracy_score=0)
        assert score.composite_score == 0.0

    async def test_mid_range(self):
        score = await scoring_service.compute_score("s1", confidence_score=50, evidence_score=50, novelty_score=50, historical_accuracy_score=50)
        assert 45 <= score.composite_score <= 55

    async def test_all_fields_present(self):
        score = await scoring_service.compute_score("sig-x", confidence_score=77, evidence_score=44, novelty_score=33, historical_accuracy_score=22)
        assert score.signal_id == "sig-x"
        assert score.confidence_score == 77.0
        assert score.evidence_score == 44.0
        assert score.novelty_score == 33.0
        assert score.historical_accuracy_score == 22.0