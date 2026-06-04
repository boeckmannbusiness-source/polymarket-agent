from typing import Any

from app.core.logging import logger
from app.schemas.signals import SignalScore


class SignalScoringService:
    async def compute_score(
        self,
        signal_id: str,
        confidence_score: float = 0.0,
        evidence_score: float = 0.0,
        novelty_score: float = 0.0,
        historical_accuracy_score: float = 0.0,
    ) -> SignalScore:
        clamped_cs = max(0.0, min(100.0, confidence_score))
        clamped_es = max(0.0, min(100.0, evidence_score))
        clamped_ns = max(0.0, min(100.0, novelty_score))
        clamped_has = max(0.0, min(100.0, historical_accuracy_score))

        composite = (
            clamped_cs * 0.40
            + clamped_es * 0.30
            + clamped_ns * 0.15
            + clamped_has * 0.15
        )
        composite = round(max(0.0, min(100.0, composite)), 2)

        return SignalScore(
            signal_id=signal_id,
            confidence_score=round(clamped_cs, 2),
            evidence_score=round(clamped_es, 2),
            novelty_score=round(clamped_ns, 2),
            historical_accuracy_score=round(clamped_has, 2),
            composite_score=composite,
        )


scoring_service = SignalScoringService()