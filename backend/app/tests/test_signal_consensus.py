import pytest
from unittest.mock import patch

from app.services.research.signal_consensus_service import SignalConsensusService, consensus_service
from app.schemas.signals import ResearchSignal, ConsensusResult


def _sig(signal_id: str, market_id: str, direction: str, outcome: str, agent_id: str, confidence: float = 0.5) -> ResearchSignal:
    return ResearchSignal(
        signal_id=signal_id,
        agent_id=agent_id,
        agent_name=f"Agent {agent_id}",
        market_id=market_id,
        market_title=f"Market {market_id}",
        direction=direction,
        outcome=outcome,
        confidence=confidence,
        rationale="test",
        evidence=[{"type": "test", "content": "test", "source": "test", "relevance": 0.5}],
    )


class TestSignalConsensusService:
    async def test_majority_support(self):
        signal = _sig("sig-1", "mkt-1", "buy", "YES", "agent-1", 0.8)
        all_signals = [
            _sig("sig-2", "mkt-1", "buy", "YES", "agent-2", 0.7),
            _sig("sig-3", "mkt-1", "buy", "YES", "agent-3", 0.6),
        ]
        result = await consensus_service.compute_consensus(signal, all_signals, {})
        assert result.approved
        assert result.consensus_type == "majority"

    async def test_majority_oppose(self):
        signal = _sig("sig-1", "mkt-1", "buy", "YES", "agent-1", 0.8)
        all_signals = [
            _sig("sig-2", "mkt-1", "sell", "NO", "agent-2", 0.7),
            _sig("sig-3", "mkt-1", "sell", "NO", "agent-3", 0.6),
        ]
        result = await consensus_service.compute_consensus(signal, all_signals, {})
        assert not result.approved

    async def test_no_other_signals_approves(self):
        signal = _sig("sig-1", "mkt-1", "buy", "YES", "agent-1", 0.8)
        result = await consensus_service.compute_consensus(signal, [], {})
        assert result.approved  # 0 supporting + 0 opposing -> score 0.5 >= 0.5

    async def test_weighted_confidence_fallback(self):
        signal = _sig("sig-1", "mkt-1", "buy", "YES", "agent-1", 0.95)
        all_signals = [
            _sig("sig-2", "mkt-1", "buy", "YES", "agent-2", 0.9),
            _sig("sig-3", "mkt-1", "sell", "NO", "agent-3", 0.8),
        ]
        result = await consensus_service.compute_consensus(signal, all_signals, {})
        # 1 supporting (sig-2), 1 opposing (sig-3)
        # majority: 1/2 = 0.5 -> approved
        assert result.approved
        assert result.supporting_agents[0]["agent_id"] == "agent-2"
        assert result.opposing_agents[0]["agent_id"] == "agent-3"

    async def test_exact_tie(self):
        signal = _sig("sig-1", "mkt-1", "buy", "YES", "agent-1", 0.5)
        all_signals = [
            _sig("sig-2", "mkt-1", "buy", "YES", "agent-2", 0.5),
            _sig("sig-3", "mkt-1", "sell", "NO", "agent-3", 0.5),
        ]
        result = await consensus_service.compute_consensus(signal, all_signals, {})
        assert result.consensus_score == 0.5
        assert result.approved

    async def test_consensus_result_has_supporting_and_opposing(self):
        signal = _sig("sig-1", "mkt-1", "buy", "YES", "agent-1", 0.8)
        all_signals = [
            _sig("sig-2", "mkt-1", "buy", "YES", "agent-2", 0.7),
            _sig("sig-3", "mkt-1", "sell", "NO", "agent-3", 0.6),
        ]
        result = await consensus_service.compute_consensus(signal, all_signals, {})
        assert len(result.supporting_agents) == 1
        assert len(result.opposing_agents) == 1
        assert result.supporting_agents[0]["agent_id"] == "agent-2"
        assert result.opposing_agents[0]["agent_id"] == "agent-3"

    async def test_consensus_score_bounds(self):
        signal = _sig("sig-1", "mkt-1", "buy", "YES", "agent-1", 0.8)
        for count in range(10):
            others = [_sig(f"s-{i}", "mkt-1", "buy" if i % 2 == 0 else "sell", "YES", f"a-{i}", 0.5) for i in range(count)]
            result = await consensus_service.compute_consensus(signal, others, {})
            assert 0 <= result.consensus_score <= 1

    async def test_different_market_ignored(self):
        signal = _sig("sig-1", "mkt-1", "buy", "YES", "agent-1", 0.8)
        all_signals = [
            _sig("sig-2", "mkt-2", "sell", "NO", "agent-2", 0.9),
        ]
        result = await consensus_service.compute_consensus(signal, all_signals, {})
        assert result.approved  # only 1 signal from different market -> 0 supporting 0 opposing -> 0.5 >= 0.5

    async def test_deterministic(self):
        signal = _sig("sig-1", "mkt-1", "buy", "YES", "agent-1", 0.8)
        all_signals = [
            _sig("sig-2", "mkt-1", "buy", "YES", "agent-2", 0.7),
            _sig("sig-3", "mkt-1", "sell", "NO", "agent-3", 0.6),
        ]
        result1 = await consensus_service.compute_consensus(signal, all_signals, {})
        result2 = await consensus_service.compute_consensus(signal, all_signals, {})
        assert result1.consensus_score == result2.consensus_score
        assert result1.approved == result2.approved