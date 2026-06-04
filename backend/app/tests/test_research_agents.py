import pytest
from unittest.mock import patch

from app.schemas.signals import ResearchSignal
from app.services.agents.news_agent import NewsAgent, news_agent
from app.services.agents.social_agent import SocialAgent, social_agent
from app.services.agents.prediction_agent import PredictionAgent, prediction_agent
from app.services.agents.market_microstructure_agent import MarketMicrostructureAgent, micro_agent
from app.services.agents.meta_research_agent import MetaResearchAgent, meta_agent


class TestBaseAgent:
    def test_agent_has_required_attributes(self):
        for agent in [news_agent, social_agent, prediction_agent, micro_agent, meta_agent]:
            assert agent.agent_id != ""
            assert agent.agent_name != ""
            assert agent.description != ""

    def test_all_agents_have_unique_ids(self):
        ids = [a.agent_id for a in [news_agent, social_agent, prediction_agent, micro_agent, meta_agent]]
        assert len(ids) == len(set(ids))

    async def test_all_agents_pass_health_check(self):
        for agent in [news_agent, social_agent, prediction_agent, micro_agent, meta_agent]:
            h = await agent.health_check()
            assert h["status"] == "healthy"
            assert h["agent_id"] == agent.agent_id


class TestNewsAgent:
    async def test_generate_signals_returns_list(self):
        signals = await news_agent.generate_signals()
        assert isinstance(signals, list)
        assert len(signals) > 0

    async def test_signals_have_required_fields(self):
        signals = await news_agent.generate_signals()
        for s in signals:
            assert s.signal_id != ""
            assert s.agent_id == "news-agent-1"
            assert s.market_id != ""
            assert s.direction in ("buy", "sell")
            assert s.outcome in ("YES", "NO")
            assert 0 <= s.confidence <= 1
            assert len(s.evidence) > 0

    async def test_signals_have_rationale(self):
        signals = await news_agent.generate_signals()
        for s in signals:
            assert s.rationale != ""
            assert "News event detected" in s.rationale

    async def test_health_check_returns_market_count(self):
        h = await news_agent.health_check()
        assert "markets_monitored" in h
        assert h["markets_monitored"] > 0


class TestSocialAgent:
    async def test_generate_signals_returns_list(self):
        signals = await social_agent.generate_signals()
        assert len(signals) > 0

    async def test_signals_have_social_evidence(self):
        signals = await social_agent.generate_signals()
        for s in signals:
            assert s.agent_id == "social-agent-1"
            types = [e["type"] for e in s.evidence]
            assert any(t in ("sentiment", "volume", "trend") for t in types)

    async def test_confidence_bounds(self):
        signals = await social_agent.generate_signals()
        for s in signals:
            assert 0 <= s.confidence <= 1


class TestPredictionAgent:
    async def test_generate_signals_returns_list(self):
        signals = await prediction_agent.generate_signals()
        assert len(signals) > 0

    async def test_signals_have_divergence_evidence(self):
        signals = await prediction_agent.generate_signals()
        for s in signals:
            types = [e["type"] for e in s.evidence]
            assert "divergence" in types

    async def test_agent_id_correct(self):
        signals = await prediction_agent.generate_signals()
        for s in signals:
            assert s.agent_id == "prediction-agent-1"


class TestMarketMicrostructureAgent:
    async def test_generate_signals_returns_list(self):
        signals = await micro_agent.generate_signals()
        assert len(signals) > 0

    async def test_signals_have_orderbook_evidence(self):
        signals = await micro_agent.generate_signals()
        for s in signals:
            types = [e["type"] for e in s.evidence]
            assert "orderbook" in types

    async def test_agent_id_correct(self):
        signals = await micro_agent.generate_signals()
        for s in signals:
            assert s.agent_id == "micro-agent-1"


class TestMetaResearchAgent:
    async def test_generate_signals_returns_empty(self):
        signals = await meta_agent.generate_signals()
        assert len(signals) == 0

    async def test_review_signals_deduplicates(self):
        s1 = _make_signal("mkt-1", "buy", "YES", "agent-1")
        s2 = _make_signal("mkt-1", "buy", "YES", "agent-2")
        s3 = _make_signal("mkt-2", "sell", "NO", "agent-1")
        deduped, removed = await meta_agent.review_signals([s1, s2, s3])
        assert len(deduped) == 2
        assert len(removed) == 1
        assert removed[0]["reason"] == "duplicate"

    async def test_review_signals_no_duplicates(self):
        s1 = _make_signal("mkt-1", "buy", "YES", "agent-1")
        s2 = _make_signal("mkt-2", "sell", "NO", "agent-2")
        deduped, removed = await meta_agent.review_signals([s1, s2])
        assert len(deduped) == 2
        assert len(removed) == 0

    async def test_detect_conflicts(self):
        s1 = _make_signal("mkt-1", "buy", "YES", "agent-1")
        s2 = _make_signal("mkt-1", "sell", "YES", "agent-2")
        conflicts = await meta_agent.detect_conflicts([s1, s2])
        assert len(conflicts) >= 1
        assert conflicts[0]["type"] == "direction_conflict"

    async def test_detect_conflicts_no_conflict(self):
        s1 = _make_signal("mkt-1", "buy", "YES", "agent-1")
        s2 = _make_signal("mkt-1", "buy", "YES", "agent-2")
        conflicts = await meta_agent.detect_conflicts([s1, s2])
        assert len(conflicts) == 0

    async def test_compute_quality_score_bounds(self):
        s = _make_signal("mkt-1", "buy", "YES", "agent-1", confidence=0.8, evidence_count=3)
        score = await meta_agent.compute_quality_score(s, [s])
        assert 0 <= score <= 100

    async def test_compute_quality_score_higher_with_more_evidence(self):
        s1 = _make_signal("mkt-1", "buy", "YES", "agent-1", confidence=0.8, evidence_count=5)
        s2 = _make_signal("mkt-2", "buy", "YES", "agent-1", confidence=0.8, evidence_count=1)
        score1 = await meta_agent.compute_quality_score(s1, [s1])
        score2 = await meta_agent.compute_quality_score(s2, [s2])
        assert score1 >= score2

    async def test_health_check(self):
        h = await meta_agent.health_check()
        assert h["status"] == "healthy"


def _make_signal(market_id: str, direction: str, outcome: str, agent_id: str, confidence: float = 0.5, evidence_count: int = 2) -> ResearchSignal:
    return ResearchSignal(
        signal_id=f"sig-{market_id}-{agent_id}",
        agent_id=agent_id,
        agent_name=f"Agent {agent_id}",
        market_id=market_id,
        market_title=f"Market {market_id}",
        direction=direction,
        outcome=outcome,
        confidence=confidence,
        rationale=f"Test signal for {market_id}",
        evidence=[{"type": "test", "content": f"evidence {i}", "source": "test", "relevance": 0.5} for i in range(evidence_count)],
    )