import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.logging import logger
from app.services.agents.base_research_agent import BaseResearchAgent
from app.schemas.signals import ResearchSignal


class MetaResearchAgent(BaseResearchAgent):
    agent_id = "meta-agent-1"
    agent_name = "Meta Research"
    description = "Reviews all generated signals, detects duplicates/conflicts, produces quality scores"

    async def generate_signals(self) -> list[ResearchSignal]:
        return []

    async def score_signal(self, signal: ResearchSignal) -> dict[str, Any]:
        return {
            "confidence_score": signal.confidence * 100,
            "evidence_score": min(100.0, len(signal.evidence) * 22.0),
            "novelty_score": 50.0,
            "historical_accuracy_score": 0.0,
            "composite_score": 0.0,
        }

    async def review_signals(self, signals: list[ResearchSignal]) -> tuple[list[ResearchSignal], list[dict[str, Any]]]:
        seen_keys: set[str] = set()
        deduped: list[ResearchSignal] = []
        removed: list[dict[str, Any]] = []

        for s in signals:
            key = f"{s.market_id}:{s.direction}:{s.outcome}"
            if key in seen_keys:
                removed.append({"signal_id": s.signal_id, "reason": "duplicate", "market_id": s.market_id, "agent_id": s.agent_id})
                logger.info("meta_removed_duplicate", signal_id=s.signal_id, market=s.market_id)
            else:
                seen_keys.add(key)
                deduped.append(s)

        return deduped, removed

    async def detect_conflicts(self, signals: list[ResearchSignal]) -> list[dict[str, Any]]:
        conflicts: list[dict[str, Any]] = []
        by_market: dict[str, list[ResearchSignal]] = {}
        for s in signals:
            by_market.setdefault(s.market_id, []).append(s)

        for mkt_id, mkt_signals in by_market.items():
            if len(mkt_signals) < 2:
                continue
            for i in range(len(mkt_signals)):
                for j in range(i + 1, len(mkt_signals)):
                    a, b = mkt_signals[i], mkt_signals[j]
                    if a.direction != b.direction and a.outcome == b.outcome:
                        conflicts.append({
                            "market_id": mkt_id,
                            "signal_a": a.signal_id,
                            "signal_b": b.signal_id,
                            "agent_a": a.agent_id,
                            "agent_b": b.agent_id,
                            "type": "direction_conflict",
                        })
        return conflicts

    async def compute_quality_score(self, signal: ResearchSignal, all_signals: list[ResearchSignal]) -> float:
        score = 50.0
        score += signal.confidence * 30.0
        evidence_count = len(signal.evidence)
        score += min(20.0, evidence_count * 5.0)

        same_agent_count = sum(1 for s in all_signals if s.agent_id == signal.agent_id and s.signal_id != signal.signal_id)
        if same_agent_count > 10:
            score -= 5.0

        score = max(0.0, min(100.0, score))
        return round(score, 2)

    async def health_check(self) -> dict[str, Any]:
        return {"agent_id": self.agent_id, "status": "healthy", "error": ""}


meta_agent = MetaResearchAgent()