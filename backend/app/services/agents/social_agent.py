import random
from datetime import datetime, timezone
from typing import Any

from app.core.logging import logger
from app.services.agents.base_research_agent import BaseResearchAgent
from app.schemas.signals import ResearchSignal

_MOCK_MARKETS = [
    {"id": "mkt-social-1", "title": "Will BTC reach $150k by July 2026?"},
    {"id": "mkt-social-2", "title": "Will ETH staking yield exceed 5% in 2026?"},
    {"id": "mkt-social-3", "title": "Will Apple stock hit $250 in 2026?"},
    {"id": "mkt-social-4", "title": "Will Trump Media reach $100 by August?"},
    {"id": "mkt-social-5", "title": "Will Dogecoin be used by more than 10M merchants?"},
    {"id": "mkt-social-6", "title": "Will Nvidia remain above $800 through June?"},
]


class SocialAgent(BaseResearchAgent):
    agent_id = "social-agent-1"
    agent_name = "Social Sentiment"
    description = "Aggregates social sentiment, trend acceleration, and narrative tracking"

    async def generate_signals(self) -> list[ResearchSignal]:
        signals: list[ResearchSignal] = []
        for mkt in _MOCK_MARKETS:
            direction = random.choice(["buy", "sell"])
            outcome = "YES" if direction == "buy" else "NO"
            confidence = random.uniform(0.35, 0.90)
            sentiment = "positive" if confidence > 0.5 else "negative"
            evidence = [
                {"type": "sentiment", "content": f"{sentiment.capitalize()} sentiment detected on X/Twitter", "source": "SocialAPI", "relevance": 0.78},
                {"type": "volume", "content": "Mention volume up 2.5x", "source": "SocialAPI", "relevance": 0.65},
                {"type": "trend", "content": "Acceleration score: 7.2/10", "source": "TrendDetection", "relevance": 0.55},
            ]
            s = self._make_signal(
                market_id=mkt["id"],
                market_title=mkt["title"],
                direction=direction,
                outcome=outcome,
                confidence=confidence,
                rationale=f"Social sentiment analysis for {mkt['title']}: {sentiment} trend detected",
                evidence=evidence,
            )
            signals.append(s)
        logger.info("social_agent_generated_signals", count=len(signals))
        return signals

    async def score_signal(self, signal: ResearchSignal) -> dict[str, Any]:
        evidence_count = len(signal.evidence)
        evidence_score = min(100.0, evidence_count * 20.0)
        return {
            "confidence_score": signal.confidence * 100,
            "evidence_score": evidence_score,
            "novelty_score": random.uniform(40.0, 90.0),
            "historical_accuracy_score": 0.0,
            "composite_score": 0.0,
        }

    async def health_check(self) -> dict[str, Any]:
        return {"agent_id": self.agent_id, "status": "healthy", "error": "", "markets_monitored": len(_MOCK_MARKETS)}

    async def get_markets(self) -> list[dict[str, Any]]:
        return _MOCK_MARKETS


social_agent = SocialAgent()