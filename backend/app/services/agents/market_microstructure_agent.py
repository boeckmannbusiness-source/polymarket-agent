import random
from typing import Any

from app.core.logging import logger
from app.services.agents.base_research_agent import BaseResearchAgent
from app.schemas.signals import ResearchSignal

_MOCK_MARKETS = [
    {"id": "mkt-micro-1", "title": "Will BTC volatility exceed 5% daily in June?"},
    {"id": "mkt-micro-2", "title": "Will ETH/BTC ratio drop below 0.04?"},
    {"id": "mkt-micro-3", "title": "Will DAI depeg below $0.98 this month?"},
    {"id": "mkt-micro-4", "title": "Will market spread exceed 2 basis points?"},
]


class MarketMicrostructureAgent(BaseResearchAgent):
    agent_id = "micro-agent-1"
    agent_name = "Market Microstructure"
    description = "Analyzes orderbook imbalance, spread, and liquidity anomalies"

    async def generate_signals(self) -> list[ResearchSignal]:
        signals: list[ResearchSignal] = []
        for mkt in _MOCK_MARKETS:
            direction = random.choice(["buy", "sell"])
            outcome = "YES" if direction == "buy" else "NO"
            confidence = random.uniform(0.4, 0.88)
            imbalance = random.uniform(-0.3, 0.3)
            spread = random.uniform(0.5, 3.0)
            evidence = [
                {"type": "orderbook", "content": f"Orderbook imbalance: {imbalance:+.3f}", "source": "OrderbookStream", "relevance": 0.91},
                {"type": "spread", "content": f"Bid-ask spread: {spread:.2f} bps", "source": "OrderbookStream", "relevance": 0.84},
                {"type": "liquidity", "content": "Liquidity depth anomaly detected", "source": "OrderbookStream", "relevance": 0.72},
            ]
            s = self._make_signal(
                market_id=mkt["id"],
                market_title=mkt["title"],
                direction=direction,
                outcome=outcome,
                confidence=confidence,
                rationale=f"Microstructure signal for {mkt['title']}: imbalance {imbalance:+.3f}",
                evidence=evidence,
            )
            signals.append(s)
        logger.info("micro_agent_generated_signals", count=len(signals))
        return signals

    async def score_signal(self, signal: ResearchSignal) -> dict[str, Any]:
        evidence_count = len(signal.evidence)
        evidence_score = min(100.0, evidence_count * 20.0)
        return {
            "confidence_score": signal.confidence * 100,
            "evidence_score": evidence_score,
            "novelty_score": random.uniform(25.0, 70.0),
            "historical_accuracy_score": 0.0,
            "composite_score": 0.0,
        }

    async def health_check(self) -> dict[str, Any]:
        return {"agent_id": self.agent_id, "status": "healthy", "error": "", "markets_monitored": len(_MOCK_MARKETS)}

    async def get_markets(self) -> list[dict[str, Any]]:
        return _MOCK_MARKETS


micro_agent = MarketMicrostructureAgent()