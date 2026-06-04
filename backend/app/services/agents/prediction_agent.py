import random
from typing import Any

from app.core.logging import logger
from app.services.agents.base_research_agent import BaseResearchAgent
from app.schemas.signals import ResearchSignal

_MOCK_MARKETS = [
    {"id": "mkt-pred-1", "title": "Will ETH surpass $5000 before July 2026?"},
    {"id": "mkt-pred-2", "title": "Will S&P 500 close above 5700 in June?"},
    {"id": "mkt-pred-3", "title": "Will Solana daily transactions exceed 50M?"},
    {"id": "mkt-pred-4", "title": "Will US 10Y yield stay above 4.5% through July?"},
]


class PredictionAgent(BaseResearchAgent):
    agent_id = "prediction-agent-1"
    agent_name = "Prediction Markets"
    description = "Analyzes probability divergences, pricing inefficiencies, and resolution estimates"

    async def generate_signals(self) -> list[ResearchSignal]:
        signals: list[ResearchSignal] = []
        for mkt in _MOCK_MARKETS:
            direction = random.choice(["buy", "sell"])
            outcome = "YES" if direction == "buy" else "NO"
            confidence = random.uniform(0.45, 0.92)
            divergence = abs(random.gauss(0, 0.08))
            evidence = [
                {"type": "divergence", "content": f"Probability divergence: {divergence:.3f}", "source": "PredictionAPI", "relevance": 0.88},
                {"type": "inefficiency", "content": "Pricing inefficiency detected in orderbook", "source": "PredictionAPI", "relevance": 0.76},
                {"type": "volume", "content": "Volume spike in this market", "source": "PredictionAPI", "relevance": 0.63},
            ]
            s = self._make_signal(
                market_id=mkt["id"],
                market_title=mkt["title"],
                direction=direction,
                outcome=outcome,
                confidence=confidence,
                rationale=f"Probability divergence {divergence:.3f} detected for {mkt['title']}",
                evidence=evidence,
            )
            signals.append(s)
        logger.info("prediction_agent_generated_signals", count=len(signals))
        return signals

    async def score_signal(self, signal: ResearchSignal) -> dict[str, Any]:
        evidence_count = len(signal.evidence)
        evidence_score = min(100.0, evidence_count * 22.0)
        return {
            "confidence_score": signal.confidence * 100,
            "evidence_score": evidence_score,
            "novelty_score": random.uniform(35.0, 75.0),
            "historical_accuracy_score": 0.0,
            "composite_score": 0.0,
        }

    async def health_check(self) -> dict[str, Any]:
        return {"agent_id": self.agent_id, "status": "healthy", "error": "", "markets_monitored": len(_MOCK_MARKETS)}

    async def get_markets(self) -> list[dict[str, Any]]:
        return _MOCK_MARKETS


prediction_agent = PredictionAgent()