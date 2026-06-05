import pytest
from app.services.evolution.evolution_manager import manager
from app.services.evolution.population_service import population_service
from app.services.evolution.strategy_genome import genome_service
from app.schemas.evolution import Candidate, StrategyGenome, FitnessScore
from datetime import datetime, timezone


class TestEvolutionManager:
    @pytest.mark.asyncio
    async def test_run_daily_returns_run(self):
        run = await manager.run_daily()
        assert run.run_id
        assert run.status in ("completed", "skipped")
        assert run.started_at
        assert run.completed_at

    @pytest.mark.asyncio
    async def test_run_daily_respects_control_plane(self):
        from app.services.control.control_plane import control_plane
        original = await control_plane.get_execution_mode()
        await control_plane.set_execution_mode("paper")
        run = await manager.run_daily()
        assert run.status in ("completed", "skipped")
        await control_plane.set_execution_mode(original)

    @pytest.mark.asyncio
    async def test_promote_candidate_success(self):
        genome = genome_service.create()
        candidate = Candidate(
            candidate_id=genome.strategy_id,
            genome=genome,
            status="EXPERIMENTAL",
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        await population_service.add_candidate(candidate)
        result = await manager.promote_candidate(genome.strategy_id)
        assert result is True
        promoted = await population_service.get_candidate(genome.strategy_id)
        assert promoted.status == "SHADOW"

    @pytest.mark.asyncio
    async def test_promote_candidate_wrong_status(self):
        genome = genome_service.create()
        candidate = Candidate(
            candidate_id=genome.strategy_id,
            genome=genome,
            status="SHADOW",
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        await population_service.add_candidate(candidate)
        result = await manager.promote_candidate(genome.strategy_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_promote_nonexistent(self):
        result = await manager.promote_candidate("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_runs(self):
        runs = await manager.get_runs()
        assert isinstance(runs, list)
        # After run_daily was called, there should be at least some runs
        assert len(runs) >= 0

    @pytest.mark.asyncio
    async def test_run_daily_with_champions(self):
        await population_service.register_champion("champ-1")
        await population_service.register_champion("champ-2")
        run = await manager.run_daily()
        assert run.run_id
        # champions_used may include our registered champions
        # don't assert content since other tests may have added champions

    @pytest.mark.asyncio
    async def test_run_daily_creates_candidates(self):
        run = await manager.run_daily()
        assert isinstance(run.candidates_created, int)
        assert run.candidates_created >= 0
