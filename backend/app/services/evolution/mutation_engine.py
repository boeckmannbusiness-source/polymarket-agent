import random
from typing import Any

from app.schemas.evolution import StrategyGenome


class MutationEngine:
    MIN_CONF = 0.1
    MAX_CONF = 0.95
    MIN_SIZING = 0.1
    MAX_SIZING = 5.0
    MIN_RISK = 0.1
    MAX_RISK = 3.0
    MUTATION_RATE = 0.3

    def mutate(self, genome: StrategyGenome, seed: int | None = None) -> StrategyGenome:
        rng = random.Random(seed) if seed is not None else random

        mutated = genome.model_copy(deep=True)
        mutations_performed = 0

        if rng.random() < self.MUTATION_RATE:
            mutated = self._mutate_confidence_threshold(mutated, rng)
            mutations_performed += 1

        if rng.random() < self.MUTATION_RATE:
            mutated = self._mutate_sizing(mutated, rng)
            mutations_performed += 1

        if rng.random() < self.MUTATION_RATE:
            mutated = self._mutate_risk(mutated, rng)
            mutations_performed += 1

        if rng.random() < self.MUTATION_RATE:
            mutated = self._mutate_consensus_mode(mutated, rng)
            mutations_performed += 1

        if rng.random() < self.MUTATION_RATE:
            mutated = self._mutate_weights(mutated, rng)
            mutations_performed += 1

        return mutated

    def mutate_with_report(self, genome: StrategyGenome, seed: int | None = None) -> tuple[StrategyGenome, list[str]]:
        rng = random.Random(seed) if seed is not None else random
        mutated = genome.model_copy(deep=True)
        changes: list[str] = []

        if rng.random() < self.MUTATION_RATE:
            old = mutated.confidence_threshold
            mutated = self._mutate_confidence_threshold(mutated, rng)
            changes.append(f"confidence_threshold: {old:.2f} -> {mutated.confidence_threshold:.2f}")

        if rng.random() < self.MUTATION_RATE:
            old = mutated.sizing_multiplier
            mutated = self._mutate_sizing(mutated, rng)
            changes.append(f"sizing_multiplier: {old:.2f} -> {mutated.sizing_multiplier:.2f}")

        if rng.random() < self.MUTATION_RATE:
            old = mutated.risk_multiplier
            mutated = self._mutate_risk(mutated, rng)
            changes.append(f"risk_multiplier: {old:.2f} -> {mutated.risk_multiplier:.2f}")

        if rng.random() < self.MUTATION_RATE:
            old_c = mutated.consensus_mode
            mutated = self._mutate_consensus_mode(mutated, rng)
            changes.append(f"consensus_mode: {old_c} -> {mutated.consensus_mode}")

        if rng.random() < self.MUTATION_RATE:
            keys_before = list(mutated.signal_weights.keys())
            mutated = self._mutate_weights(mutated, rng)
            changes.append(f"signal_weights mutated for {len(keys_before)} keys")

        return mutated, changes

    def _mutate_confidence_threshold(self, genome: StrategyGenome, rng: random.Random) -> StrategyGenome:
        delta = rng.uniform(-0.15, 0.15)
        new_val = genome.confidence_threshold + delta
        genome.confidence_threshold = round(max(self.MIN_CONF, min(self.MAX_CONF, new_val)), 2)
        return genome

    def _mutate_sizing(self, genome: StrategyGenome, rng: random.Random) -> StrategyGenome:
        delta = rng.uniform(-0.5, 0.5)
        new_val = genome.sizing_multiplier + delta
        genome.sizing_multiplier = round(max(self.MIN_SIZING, min(self.MAX_SIZING, new_val)), 2)
        return genome

    def _mutate_risk(self, genome: StrategyGenome, rng: random.Random) -> StrategyGenome:
        delta = rng.uniform(-0.3, 0.3)
        new_val = genome.risk_multiplier + delta
        genome.risk_multiplier = round(max(self.MIN_RISK, min(self.MAX_RISK, new_val)), 2)
        return genome

    def _mutate_consensus_mode(self, genome: StrategyGenome, rng: random.Random) -> StrategyGenome:
        modes = ["majority", "weighted_confidence", "weighted_accuracy"]
        available = [m for m in modes if m != genome.consensus_mode]
        if available:
            genome.consensus_mode = rng.choice(available)
        return genome

    def _mutate_weights(self, genome: StrategyGenome, rng: random.Random) -> StrategyGenome:
        for k in genome.signal_weights:
            if rng.random() < 0.4:
                delta = rng.uniform(-0.3, 0.3)
                new_w = genome.signal_weights[k] + delta
                genome.signal_weights[k] = round(max(0.0, min(2.0, new_w)), 4)
        return genome


mutation_engine = MutationEngine()