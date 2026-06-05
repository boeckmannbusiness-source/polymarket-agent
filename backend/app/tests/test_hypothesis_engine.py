import pytest
from app.services.research.hypothesis_engine import hypothesis_engine


class TestHypothesisEngine:
    @pytest.mark.asyncio
    async def test_propose(self):
        h = hypothesis_engine.propose("Test hypothesis", "Description", tags=["test"])
        assert h.status == "PROPOSED"
        assert h.confidence == 0.0
        assert h.hypothesis_id
        assert "test" in h.tags

    @pytest.mark.asyncio
    async def test_start_testing(self):
        h = hypothesis_engine.propose("Testing lifecycle", "Desc")
        result = await hypothesis_engine.start_testing(h.hypothesis_id)
        assert result is not None
        assert result.status == "TESTING"

    @pytest.mark.asyncio
    async def test_validate(self):
        h = hypothesis_engine.propose("Validate test", "Desc")
        result = await hypothesis_engine.validate(h.hypothesis_id, evidence=["Found evidence"], confidence=0.95)
        assert result is not None
        assert result.status == "VALIDATED"
        assert result.confidence == 0.95
        assert "Found evidence" in result.evidence

    @pytest.mark.asyncio
    async def test_reject(self):
        h = hypothesis_engine.propose("Reject test", "Desc")
        result = await hypothesis_engine.reject(h.hypothesis_id, reason="Insufficient evidence")
        assert result is not None
        assert result.status == "REJECTED"
        assert "Insufficient evidence" in result.evidence

    @pytest.mark.asyncio
    async def test_archive(self):
        h = hypothesis_engine.propose("Archive test", "Desc")
        result = await hypothesis_engine.archive(h.hypothesis_id)
        assert result is not None
        assert result.status == "ARCHIVED"

    @pytest.mark.asyncio
    async def test_get_by_status(self):
        h1 = hypothesis_engine.propose("Get by status 1", "Desc")
        h2 = hypothesis_engine.propose("Get by status 2", "Desc")
        await hypothesis_engine.validate(h1.hypothesis_id)
        await hypothesis_engine.reject(h2.hypothesis_id)
        validated = await hypothesis_engine.get_by_status("VALIDATED")
        rejected = await hypothesis_engine.get_by_status("REJECTED")
        assert len(validated) >= 1
        assert len(rejected) >= 1

    @pytest.mark.asyncio
    async def test_update_nonexistent(self):
        result = await hypothesis_engine.start_testing("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        h = hypothesis_engine.propose("Full lifecycle", "Desc")
        assert h.status == "PROPOSED"
        await hypothesis_engine.start_testing(h.hypothesis_id)
        h2 = await hypothesis_engine.get_by_status("TESTING")
        assert any(hh.hypothesis_id == h.hypothesis_id for hh in h2)
        await hypothesis_engine.validate(h.hypothesis_id, confidence=0.85)
        h3 = await hypothesis_engine.get_by_status("VALIDATED")
        assert any(hh.hypothesis_id == h.hypothesis_id for hh in h3)
        await hypothesis_engine.archive(h.hypothesis_id)
        h4 = await hypothesis_engine.get_by_status("ARCHIVED")
        assert any(hh.hypothesis_id == h.hypothesis_id for hh in h4)
