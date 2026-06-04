import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone

from app.services.research.research_orchestrator import ResearchOrchestrator, orchestrator, ALL_AGENTS
from app.services.research.signal_registry import signal_registry
from app.services.agents.news_agent import news_agent
from app.services.agents.social_agent import social_agent


@pytest.fixture(autouse=True)
def _no_redis():
    with patch("app.services.research.signal_registry.SignalRegistry._safe_redis", return_value=None):
        with patch("app.services.shadow.shadow_execution_service.ShadowExecutionService._safe_redis", return_value=None):
            with patch("app.services.research.research_orchestrator.ControlPlane.get_state", return_value={"trading_enabled": True}):
                with patch("app.services.audit.audit_logger._persist_to_redis"):
                    yield


class TestResearchOrchestrator:
    async def test_run_pipeline_returns_results(self, _no_redis):
        await orchestrator.reset()
        result = await orchestrator.run_pipeline()
        assert "started_at" in result
        assert "agents_run" in result
        assert result["agents_run"] > 0
        assert "completed_at" in result

    async def test_run_pipeline_generates_signals(self, _no_redis):
        await orchestrator.reset()
        result = await orchestrator.run_pipeline()
        assert result["signals_generated"] > 0
        assert result["signals_after_meta"] > 0

    async def test_run_pipeline_approved_or_rejected(self, _no_redis):
        await orchestrator.reset()
        result = await orchestrator.run_pipeline()
        approved = result.get("approved", 0)
        rejected = result.get("rejected", 0)
        assert approved >= 0
        assert rejected >= 0
        assert approved + rejected > 0

    async def test_registry_has_entries_after_pipeline(self, _no_redis):
        await orchestrator.reset()
        await orchestrator.run_pipeline()
        count = await signal_registry.count()
        assert count > 0

    async def test_run_count_increments(self, _no_redis):
        await orchestrator.reset()
        s1 = await orchestrator.run_pipeline()
        s2 = await orchestrator.run_pipeline()
        assert s2["run_count"] > s1["run_count"]

    async def test_get_status_returns_data(self, _no_redis):
        await orchestrator.reset()
        await orchestrator.run_pipeline()
        status = await orchestrator.get_status()
        assert "last_run" in status
        assert "run_count" in status
        assert "stats" in status

    async def test_get_agent_health(self, _no_redis):
        health = await orchestrator.get_agent_health()
        assert len(health) == len(ALL_AGENTS)
        for h in health:
            assert "agent_id" in h
            assert "status" in h


class TestResearchOrchestratorControlPlane:
    async def test_skips_when_trading_disabled(self, _no_redis):
        with patch("app.services.research.research_orchestrator.ControlPlane.get_state", return_value={"trading_enabled": False}):
            await orchestrator.reset()
            result = await orchestrator.run_pipeline()
            assert result["status"] == "skipped"
            assert result["reason"] == "trading_disabled"


class TestSignalRegistry:
    async def test_register_creates_entry(self):
        await signal_registry.reset()
        sig = _make_signal("test-1")
        entry = await signal_registry.register(sig, quality_score=75.0)
        assert entry.signal_id == sig.signal_id
        assert entry.quality_score == 75.0
        assert entry.lifecycle == "generated"

    async def test_get_all_returns_entries(self):
        await signal_registry.reset()
        sig1 = _make_signal("s1")
        sig2 = _make_signal("s2")
        await signal_registry.register(sig1)
        await signal_registry.register(sig2)
        all_ = await signal_registry.get_all()
        assert len(all_) == 2

    async def test_update_lifecycle(self):
        await signal_registry.reset()
        sig = _make_signal("test-1")
        entry = await signal_registry.register(sig)
        updated = await signal_registry.update_lifecycle(sig.signal_id, "consensus_approved", "promoted")
        assert updated is not None
        assert updated.lifecycle == "consensus_approved"
        assert updated.promotion_state == "promoted"

    async def test_get_stats(self):
        await signal_registry.reset()
        sig1 = _make_signal("s1")
        sig2 = _make_signal("s2")
        await signal_registry.register(sig1)
        await signal_registry.register(sig2)
        stats = await signal_registry.get_stats()
        assert stats["total_signals"] == 2
        assert stats["avg_confidence"] > 0

    async def test_get_nonexistent(self):
        await signal_registry.reset()
        e = await signal_registry.get("nonexistent")
        assert e is None

    async def test_get_agent_counts(self):
        await signal_registry.reset()
        sig = _make_signal("s1", agent_id="agent-x")
        await signal_registry.register(sig)
        counts = await signal_registry.get_agent_counts()
        assert len(counts) >= 1
        assert counts[0]["total"] >= 1


class TestOrchestratorPipeline:
    async def test_duplicates_removed_count(self, _no_redis):
        await orchestrator.reset()

        class DupAgent:
            agent_id = "dup-agent"
            agent_name = "Duplicate Agent"
            description = ""

            async def generate_signals(self):
                return [_make_signal("mkt-1")]

            async def health_check(self):
                return {"agent_id": "dup-agent", "status": "healthy"}

        with patch.object(orchestrator.__class__, "_AGENTS", {"dup": DupAgent()}, create=True), \
             patch.object(orchestrator.__class__, "ALL_AGENTS", [DupAgent()], create=True):
            result = await orchestrator.run_pipeline()
            assert result.get("duplicates_removed", 0) >= 0

    async def test_audit_log_emitted_on_run(self, _no_redis):
        from unittest.mock import patch, AsyncMock
        mock_emit = AsyncMock()
        with patch("app.services.research.research_orchestrator.audit_emit", mock_emit, create=True):
            await orchestrator.reset()
            result = await orchestrator.run_pipeline()
            mock_emit.assert_called_once()
            args = mock_emit.call_args[0]
            assert args[0] == "orchestrator.run"


def _make_signal(suffix: str = "1", agent_id: str = "test-agent", market_id: str = "mkt-1", direction: str = "buy", outcome: str = "YES", confidence: float = 0.7) -> ResearchSignal:
    from app.schemas.signals import ResearchSignal
    return ResearchSignal(
        signal_id=f"sig-{suffix}",
        agent_id=agent_id,
        agent_name=f"Test Agent {agent_id}",
        market_id=market_id,
        market_title=f"Test Market {market_id}",
        direction=direction,
        outcome=outcome,
        confidence=confidence,
        rationale=f"Test rationale for {suffix}",
        evidence=[{"type": "test", "content": f"Evidence {i}", "source": "test", "relevance": 0.5} for i in range(2)],
    )


from app.schemas.signals import ResearchSignal