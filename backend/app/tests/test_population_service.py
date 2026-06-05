import pytest
from app.services.evolution.population_service import population_service
from app.schemas.evolution import Candidate, StrategyGenome, FitnessScore, LineageNode
from datetime import datetime, timezone


class TestPopulationService:
    @pytest.mark.asyncio
    async def test_add_and_get_candidate(self):
        genome = StrategyGenome(strategy_id="pop-test-1", archetype="momentum", confidence_threshold=0.5, created_at=datetime.now(timezone.utc).isoformat())
        candidate = Candidate(candidate_id="pop-test-1", genome=genome, status="EXPERIMENTAL", created_at=datetime.now(timezone.utc).isoformat(), updated_at=datetime.now(timezone.utc).isoformat())
        await population_service.add_candidate(candidate)
        retrieved = await population_service.get_candidate("pop-test-1")
        assert retrieved is not None
        assert retrieved.candidate_id == "pop-test-1"
        assert retrieved.status == "EXPERIMENTAL"
        assert retrieved.genome.archetype == "momentum"

    @pytest.mark.asyncio
    async def test_update_candidate_fitness(self):
        genome = StrategyGenome(strategy_id="pop-test-fitness", archetype="test", created_at=datetime.now(timezone.utc).isoformat())
        candidate = Candidate(candidate_id="pop-test-fitness", genome=genome, status="EXPERIMENTAL", created_at=datetime.now(timezone.utc).isoformat(), updated_at=datetime.now(timezone.utc).isoformat())
        await population_service.add_candidate(candidate)
        fitness = FitnessScore(strategy_id="pop-test-fitness", composite_fitness=85.5)
        await population_service.update_candidate_fitness("pop-test-fitness", fitness)
        retrieved = await population_service.get_candidate("pop-test-fitness")
        assert retrieved.fitness is not None
        assert retrieved.fitness.composite_fitness == 85.5

    @pytest.mark.asyncio
    async def test_update_candidate_status(self):
        genome = StrategyGenome(strategy_id="pop-test-status", archetype="test", created_at=datetime.now(timezone.utc).isoformat())
        candidate = Candidate(candidate_id="pop-test-status", genome=genome, status="EXPERIMENTAL", created_at=datetime.now(timezone.utc).isoformat(), updated_at=datetime.now(timezone.utc).isoformat())
        await population_service.add_candidate(candidate)
        await population_service.update_candidate_status("pop-test-status", "SHADOW")
        retrieved = await population_service.get_candidate("pop-test-status")
        assert retrieved.status == "SHADOW"

    @pytest.mark.asyncio
    async def test_get_nonexistent_candidate(self):
        result = await population_service.get_candidate("does-not-exist")
        assert result is None

    @pytest.mark.asyncio
    async def test_register_and_get_champions(self):
        await population_service.register_champion("champion-1")
        champions = await population_service.get_champions()
        assert isinstance(champions, list)

    @pytest.mark.asyncio
    async def test_get_population(self):
        pop = await population_service.get_population()
        assert isinstance(pop, list)

    @pytest.mark.asyncio
    async def test_get_lineage(self):
        lineage = await population_service.get_lineage()
        assert isinstance(lineage, list)

    @pytest.mark.asyncio
    async def test_record_and_get_generations(self):
        gen_data = {"run_id": "gen-test", "candidates": 5}
        await population_service.record_generation(gen_data)
        gens = await population_service.get_generations()
        assert isinstance(gens, list)
        found = any(g.get("run_id") == "gen-test" for g in gens)
        assert found
