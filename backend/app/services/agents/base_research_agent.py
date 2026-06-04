import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.logging import logger
from app.schemas.signals import ResearchSignal


class BaseResearchAgent:
    agent_id: str = ""
    agent_name: str = ""
    description: str = ""

    async def generate_signals(self) -> list[ResearchSignal]:
        raise NotImplementedError

    async def score_signal(self, signal: ResearchSignal) -> dict[str, Any]:
        return {
            "confidence_score": signal.confidence,
            "evidence_score": 50.0,
            "novelty_score": 50.0,
            "historical_accuracy_score": 0.0,
            "composite_score": 0.0,
        }

    async def explain_signal(self, signal: ResearchSignal) -> str:
        return signal.rationale

    async def health_check(self) -> dict[str, Any]:
        return {"agent_id": self.agent_id, "status": "healthy", "error": ""}

    def _make_signal(
        self,
        market_id: str,
        market_title: str,
        direction: str,
        outcome: str,
        confidence: float,
        rationale: str,
        evidence: list[dict[str, Any]] | None = None,
    ) -> ResearchSignal:
        return ResearchSignal(
            signal_id=str(uuid.uuid4())[:16],
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            market_id=market_id,
            market_title=market_title,
            direction=direction,
            outcome=outcome.upper(),
            confidence=round(max(0.0, min(1.0, confidence)), 4),
            rationale=rationale,
            evidence=evidence or [],
            created_at=datetime.now(timezone.utc).isoformat(),
        )