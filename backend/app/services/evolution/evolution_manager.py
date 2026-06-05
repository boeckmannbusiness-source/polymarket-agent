import uuid
import random
from datetime import datetime, timezone
from typing import Any

from app.services.evolution.fitness_calculator import fitness_calculator
from app.services.evolution.strategy_factory import factory
from app.services.evolution.mutation_engine import mutation_engine
from app.services.evolution.crossover_engine import crossover_engine
from app.services.evolution.population_service import population_service
from app.services.evolution.strategy_genome import genome_service
from app.schemas.evolution import StrategyGenome, Candidate, EvolutionRun
from app.services.control.control_plane import control_plane
from app.services.audit.audit_logger import emit as audit_emit


class EvolutionManager:
    def __init__(self):
        self._runs: list[EvolutionRun] = []

    async def run_daily(self) -> EvolutionRun:
        run_id = f"evolution-{str(uuid.uuid4())[:8]}"
        started_at = datetime.now(timezone.utc).isoformat()
        await audit_emit("evolution.run.start", "evolution", "system", {"run_id": run_id})

        execution_mode = await self._safe_read_execution_mode()
        if execution_mode == "disabled":
            await audit_emit("evolution.run.skipped", "evolution", "system", {"run_id": run_id, "reason": "execution_disabled"})
            run = EvolutionRun(run_id=run_id, started_at=started_at, completed_at=datetime.now(timezone.utc).isoformat(), status="skipped")
            self._runs.append(run)
            return run

        champions = await population_service.get_champions()
        candidates_created = 0
        mutations_performed = 0
        crossovers_performed = 0
        new_candidates: list[Candidate] = []

        for champion_id in champions:
            raw = await population_service.get_candidate(champion_id)
            if raw and raw.genome:
                mutated, changes = mutation_engine.mutate_with_report(raw.genome, seed=hash(champion_id) % (2**31))
                mutations_performed += len(changes)
                child = genome_service.clone_from(mutated, new_id=f"ev-mut-{str(uuid.uuid4())[:8]}")
                candidate = Candidate(
                    candidate_id=child.strategy_id,
                    genome=child,
                    status="EXPERIMENTAL",
                    created_at=datetime.now(timezone.utc).isoformat(),
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
                await population_service.add_candidate(candidate)
                new_candidates.append(candidate)
                candidates_created += 1

        if len(champions) >= 2:
            pairs = list(zip(champions[:-1], champions[1:]))
            for pair in pairs[:3]:
                a_raw = await population_service.get_candidate(pair[0])
                b_raw = await population_service.get_candidate(pair[1])
                if a_raw and a_raw.genome and b_raw and b_raw.genome:
                    child, report = crossover_engine.crossover(a_raw.genome, b_raw.genome, seed=hash(pair) % (2**31))
                    crossovers_performed += 1
                    candidate = Candidate(
                        candidate_id=child.strategy_id,
                        genome=child,
                        status="EXPERIMENTAL",
                        created_at=datetime.now(timezone.utc).isoformat(),
                        updated_at=datetime.now(timezone.utc).isoformat(),
                    )
                    await population_service.add_candidate(candidate)
                    new_candidates.append(candidate)
                    candidates_created += 1

        for _ in range(2):
            candidate = await factory.create_exploration()
            await population_service.add_candidate(candidate)
            new_candidates.append(candidate)
            candidates_created += 1

        for candidate in new_candidates:
            fitness = fitness_calculator.compute(
                sharpe=random.uniform(-1.0, 2.0),
                sortino=random.uniform(-1.0, 2.0),
                alpha=random.uniform(-0.5, 0.5),
                drawdown=random.uniform(0.0, 0.3),
                confidence=random.uniform(0.3, 0.9),
                health=random.uniform(50.0, 95.0),
                promotion=random.uniform(0.0, 1.0),
            )
            fitness.strategy_id = candidate.candidate_id
            await population_service.update_candidate_fitness(candidate.candidate_id, fitness)

        await population_service.record_generation({
            "run_id": run_id,
            "timestamp": started_at,
            "candidates_created": candidates_created,
            "mutations": mutations_performed,
            "crossovers": crossovers_performed,
            "champions_used": champions,
        })

        completed_at = datetime.now(timezone.utc).isoformat()
        run = EvolutionRun(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            candidates_created=candidates_created,
            mutations_performed=mutations_performed,
            crossovers_performed=crossovers_performed,
            champions_used=champions,
            status="completed",
        )
        self._runs.append(run)
        await audit_emit("evolution.run.complete", "evolution", "system", {
            "run_id": run_id, "candidates": candidates_created,
            "mutations": mutations_performed, "crossovers": crossovers_performed,
        })
        return run

    async def get_runs(self) -> list[EvolutionRun]:
        return list(self._runs)

    async def _safe_read_execution_mode(self) -> str:
        try:
            return await control_plane.get_execution_mode()
        except Exception:
            return "shadow"

    async def promote_candidate(self, candidate_id: str) -> bool:
        candidate = await population_service.get_candidate(candidate_id)
        if not candidate:
            return False
        if candidate.status != "EXPERIMENTAL":
            return False
        await population_service.update_candidate_status(candidate_id, "SHADOW")
        await audit_emit("evolution.promote", "evolution", "system", {
            "candidate_id": candidate_id, "new_status": "SHADOW",
        })
        return True


manager = EvolutionManager()