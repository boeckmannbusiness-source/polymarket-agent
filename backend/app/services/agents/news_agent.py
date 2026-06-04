import random
from datetime import datetime, timezone
from typing import Any

from app.core.logging import logger
from app.services.agents.base_research_agent import BaseResearchAgent
from app.schemas.signals import ResearchSignal

_MOCK_MARKETS = [
    {"id": "mkt-news-1", "title": "Will Fed cut rates in June 2026?"},
    {"id": "mkt-news-2", "title": "Will oil exceed $100/barrel in Q3 2026?"},
    {"id": "mkt-news-3", "title": "Will US GDP growth exceed 2.5% in 2026?"},
    {"id": "mkt-news-4", "title": "Will tech sector rally continue through June?"},
    {"id": "mkt-news-5", "title": "Will unemployment stay below 4% through 2026?"},
]


class NewsAgent(BaseResearchAgent):
    agent_id = "news-agent-1"
    agent_name = "News Intelligence"
    description = "Analyzes market news, events, and catalysts"

    async def generate_signals(self) -> list[ResearchSignal]:
        signals: list[ResearchSignal] = []
        for mkt in _MOCK_MARKETS:
            direction = random.choice(["buy", "sell"])
            outcome = "YES" if direction == "buy" else "NO"
            confidence = random.uniform(0.4, 0.95)
            evidence = [
                {"type": "headline", "content": f"Breaking: {mkt['title']} catalyst detected", "source": "Reuters", "relevance": 0.85},
                {"type": "sentiment", "content": "Positive sentiment shift detected", "source": "NewsAPI", "relevance": 0.72},
                {"type": "volume", "content": "Article volume up 3.2x in past 24h", "source": "NewsAPI", "relevance": 0.61},
            ]
            s = self._make_signal(
                market_id=mkt["id"],
                market_title=mkt["title"],
                direction=direction,
                outcome=outcome,
                confidence=confidence,
                rationale=f"News event detected for {mkt['title']}: catalyst score {confidence:.2f}",
                evidence=evidence,
            )
            signals.append(s)
        logger.info("news_agent_generated_signals", count=len(signals))
        return signals

    async def score_signal(self, signal: ResearchSignal) -> dict[str, Any]:
        evidence_count = len(signal.evidence)
        evidence_score = min(100.0, evidence_count * 25.0)
        return {
            "confidence_score": signal.confidence * 100,
            "evidence_score": evidence_score,
            "novelty_score": random.uniform(30.0, 80.0),
            "historical_accuracy_score": 0.0,
            "composite_score": 0.0,
        }

    async def health_check(self) -> dict[str, Any]:
        return {"agent_id": self.agent_id, "status": "healthy", "error": "", "markets_monitored": len(_MOCK_MARKETS)}

    async def get_markets(self) -> list[dict[str, Any]]:
        return _MOCK_MARKETS


news_agent = NewsAgent()