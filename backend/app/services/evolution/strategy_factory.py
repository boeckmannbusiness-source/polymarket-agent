import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.evolution import StrategyGenome, Candidate, FitnessScore
from app.services.evolution.strategy_genome import genome_service


class StrategyFactory:
    async def create_from_champion(
        self,
        champion_id: str,
        champion_genome: StrategyGenome | None = None,
        fitness: FitnessScore | None = None,
    ) -> Candidate:
        genome = genome_service.clone_from(champion_genome) if champion_genome else genome_service.create(archetype="champion_descendant", parent_ids=[champion_id], generation=1)
        return Candidate(
            candidate_id=genome.strategy_id,
            genome=genome,
            status="EXPERIMENTAL",
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            fitness=fitness,
        )

    async def create_exploration(self) -> Candidate:
        import random
        archetypes = ["momentum", "mean_reversion", "breakout", "trend_following", "volatility"]
        archetype = random.choice(archetypes)
        conf_threshold = round(random.uniform(0.3, 0.8), 2)
        sizing = round(random.uniform(0.5, 2.0), 2)
        risk = round(random.uniform(0.3, 1.5), 2)
        modes = ["majority", "weighted_confidence"]
        genome = genome_service.create(
            archetype=archetype,
            confidence_threshold=conf_threshold,
            sizing_multiplier=sizing,
            risk_multiplier=risk,
            consensus_mode=random.choice(modes),
        )
        return Candidate(
            candidate_id=genome.strategy_id,
            genome=genome,
            status="EXPERIMENTAL",
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    async def create_hybrid(
        self,
        parent_a_id: str,
        parent_b_id: str,
        genome_a: StrategyGenome,
        genome_b: StrategyGenome,
    ) -> Candidate:
        import random
        weights = {}
        all_keys = set(genome_a.signal_weights.keys()) | set(genome_b.signal_weights.keys())
        for k in all_keys:
            w_a = genome_a.signal_weights.get(k, 0.5)
            w_b = genome_b.signal_weights.get(k, 0.5)
            weights[k] = round(random.choice([w_a, w_b]), 4)

        conf = round(random.choice([genome_a.confidence_threshold, genome_b.confidence_threshold]), 2)
        sizing = round(random.choice([genome_a.sizing_multiplier, genome_b.sizing_multiplier]), 2)
        risk = round(random.choice([genome_a.risk_multiplier, genome_b.risk_multiplier]), 2)
        mode = random.choice([genome_a.consensus_mode, genome_b.consensus_mode])

        genome = StrategyGenome(
            strategy_id=str(uuid.uuid4())[:16],
            parent_ids=[parent_a_id, parent_b_id],
            generation=max(genome_a.generation, genome_b.generation) + 1,
            archetype=f"hybrid:{genome_a.archetype}:{genome_b.archetype}",
            signal_weights=weights,
            confidence_threshold=conf,
            sizing_multiplier=sizing,
            risk_multiplier=risk,
            consensus_mode=mode,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return Candidate(
            candidate_id=genome.strategy_id,
            genome=genome,
            status="EXPERIMENTAL",
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )


factory = StrategyFactory()