import pytest
from app.services.research.research_memory import research_memory
from app.schemas.research_memory import ResearchMemoryEntry, HypothesisRecord, RegimeSnapshot
from datetime import datetime, timezone


class TestResearchMemory:
    @pytest.mark.asyncio
    async def test_store_and_get_memory(self):
        entry = ResearchMemoryEntry(
            entry_id="mem-1", entry_type="hypothesis_winning",
            tags=["momentum", "trend"], content="Momentum strategies work in trending markets",
            confidence=0.85, created_at=datetime.now(timezone.utc).isoformat(),
        )
        await research_memory.store(entry)
        entries = await research_memory.get_memory()
        assert len(entries) >= 1
        found = any(e.entry_id == "mem-1" for e in entries)
        assert found

    @pytest.mark.asyncio
    async def test_get_memory_by_type(self):
        entries = await research_memory.get_memory(entry_type="hypothesis_winning")
        assert all(e.entry_type == "hypothesis_winning" for e in entries)

    @pytest.mark.asyncio
    async def test_add_and_get_hypothesis(self):
        hyp = HypothesisRecord(
            hypothesis_id="hyp-test-1", title="Test Hypothesis",
            description="Testing hypothesis lifecycle", status="PROPOSED",
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        await research_memory.add_hypothesis(hyp)
        hypotheses = await research_memory.get_hypotheses()
        found = any(h.hypothesis_id == "hyp-test-1" for h in hypotheses)
        assert found

    @pytest.mark.asyncio
    async def test_update_hypothesis(self):
        hyp = HypothesisRecord(
            hypothesis_id="hyp-update-1", title="Update Test",
            description="Testing update", status="PROPOSED",
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        await research_memory.add_hypothesis(hyp)
        updated = await research_memory.update_hypothesis("hyp-update-1", status="VALIDATED", confidence=0.9)
        assert updated is not None
        assert updated.status == "VALIDATED"
        assert updated.confidence == 0.9

    @pytest.mark.asyncio
    async def test_record_and_get_regimes(self):
        snap = RegimeSnapshot(regime="trending", confidence=0.8, detected_at=datetime.now(timezone.utc).isoformat())
        await research_memory.record_regime(snap)
        regimes = await research_memory.get_regimes()
        assert len(regimes) >= 1
        assert regimes[-1].regime == "trending"

    @pytest.mark.asyncio
    async def test_get_current_regime(self):
        snap1 = RegimeSnapshot(regime="low_volatility", confidence=0.7, detected_at=datetime.now(timezone.utc).isoformat())
        snap2 = RegimeSnapshot(regime="high_volatility", confidence=0.9, detected_at=datetime.now(timezone.utc).isoformat())
        await research_memory.record_regime(snap1)
        await research_memory.record_regime(snap2)
        current = await research_memory.get_current_regime()
        assert current is not None
        assert current.regime == "high_volatility"

    @pytest.mark.asyncio
    async def test_update_nonexistent_hypothesis(self):
        result = await research_memory.update_hypothesis("nonexistent", status="VALIDATED")
        assert result is None
