import pytest
from app.services.research.strategy_generator import strategy_generator


class TestStrategyGenerator:
    @pytest.mark.asyncio
    async def test_mutate_top_performers(self):
        top = [{"strategy_id": "s1", "archetype": "momentum", "generation": 3},
               {"strategy_id": "s2", "archetype": "mean_reversion", "generation": 2}]
        recs = await strategy_generator.mutate_top_performers(top, count=2)
        assert len(recs) <= 2
        for r in recs:
            assert r.candidate_id
            assert "mutated" in r.archetype

    @pytest.mark.asyncio
    async def test_recombine_champions(self):
        champs = [{"strategy_id": "c1", "archetype": "trend", "generation": 5},
                  {"strategy_id": "c2", "archetype": "breakout", "generation": 4}]
        recs = await strategy_generator.recombine_champions(champs)
        assert len(recs) >= 1
        for r in recs:
            assert "recombined" in r.archetype

    @pytest.mark.asyncio
    async def test_recombine_insufficient(self):
        recs = await strategy_generator.recombine_champions([{"strategy_id": "c1"}])
        assert len(recs) == 0

    @pytest.mark.asyncio
    async def test_generate_contrarian(self):
        recs = await strategy_generator.generate_contrarian(count=2)
        assert len(recs) == 2
        for r in recs:
            assert r.archetype == "contrarian"
            assert r.novelty_score >= 0.6

    @pytest.mark.asyncio
    async def test_generate_regime_specific(self):
        recs = await strategy_generator.generate_regime_specific("trending", count=1)
        assert len(recs) == 1
        assert "regime:trend_following" in recs[0].archetype

    @pytest.mark.asyncio
    async def test_generate_novel(self):
        recs = await strategy_generator.generate_novel(count=3)
        assert len(recs) == 3
        for r in recs:
            assert "novel:" in r.archetype
            assert r.novelty_score >= 0.8

    @pytest.mark.asyncio
    async def test_generate_unknown_regime(self):
        recs = await strategy_generator.generate_regime_specific("unknown_regime", count=1)
        assert recs[0].archetype == "regime:exploration"
