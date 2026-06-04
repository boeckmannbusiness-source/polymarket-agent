from datetime import datetime, timezone
from typing import Any

from app.core.logging import logger
from app.schemas.signals import ResearchSignal, ConsensusResult


class SignalConsensusService:
    MIN_CONSENSUS_THRESHOLD = 0.50

    async def compute_consensus(
        self,
        signal: ResearchSignal,
        all_signals: list[ResearchSignal],
        agent_scores: dict[str, dict[str, Any]],
    ) -> ConsensusResult:
        same_market = [s for s in all_signals if s.market_id == signal.market_id and s.signal_id != signal.signal_id]
        supporting = []
        opposing = []

        for s in same_market:
            score_data = agent_scores.get(s.agent_id, {"composite_score": 50.0})
            entry = {
                "agent_id": s.agent_id,
                "agent_name": s.agent_name,
                "signal_id": s.signal_id,
                "direction": s.direction,
                "outcome": s.outcome,
                "confidence": s.confidence,
                "composite_score": score_data.get("composite_score", 50.0),
            }
            if s.direction == signal.direction and s.outcome == signal.outcome:
                supporting.append(entry)
            else:
                opposing.append(entry)

        consensus_score, consensus_type = self._majority_vote(signal, supporting, opposing)

        if consensus_score < self.MIN_CONSENSUS_THRESHOLD:
            alt_score, alt_type = self._weighted_confidence(signal, supporting, opposing, agent_scores)
            if alt_score > consensus_score:
                consensus_score = alt_score
                consensus_type = alt_type

        if consensus_score < self.MIN_CONSENSUS_THRESHOLD:
            alt_score, alt_type = self._weighted_accuracy(signal, supporting, opposing, agent_scores)
            if alt_score > consensus_score:
                consensus_score = alt_score
                consensus_type = alt_type

        result = ConsensusResult(
            signal=signal,
            supporting_agents=supporting,
            opposing_agents=opposing,
            consensus_score=round(consensus_score, 4),
            consensus_type=consensus_type,
            approved=consensus_score >= self.MIN_CONSENSUS_THRESHOLD,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info("consensus_computed", signal_id=signal.signal_id, approved=result.approved, score=result.consensus_score, type=result.consensus_type)
        return result

    def _majority_vote(self, signal: ResearchSignal, supporting: list[dict], opposing: list[dict]) -> tuple[float, str]:
        total = len(supporting) + len(opposing)
        if total == 0:
            return 0.5, "majority"
        score = len(supporting) / total
        return score, "majority"

    def _weighted_confidence(self, signal: ResearchSignal, supporting: list[dict], opposing: list[dict], agent_scores: dict) -> tuple[float, str]:
        supporting_weight = sum(s["confidence"] for s in supporting)
        opposing_weight = sum(o["confidence"] for o in opposing)
        total_weight = supporting_weight + opposing_weight
        if total_weight == 0:
            return 0.5, "weighted_confidence"
        score = supporting_weight / total_weight
        return score, "weighted_confidence"

    def _weighted_accuracy(self, signal: ResearchSignal, supporting: list[dict], opposing: list[dict], agent_scores: dict) -> tuple[float, str]:
        supporting_weight = sum(agent_scores.get(s["agent_id"], {}).get("composite_score", 50.0) / 100.0 * s["confidence"] for s in supporting)
        opposing_weight = sum(agent_scores.get(o["agent_id"], {}).get("composite_score", 50.0) / 100.0 * o["confidence"] for o in opposing)
        total_weight = supporting_weight + opposing_weight
        if total_weight == 0:
            return 0.5, "weighted_accuracy"
        score = supporting_weight / total_weight
        return score, "weighted_accuracy"


consensus_service = SignalConsensusService()