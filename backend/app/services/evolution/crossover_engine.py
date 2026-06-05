import random
from typing import Any

from app.schemas.evolution import StrategyGenome, CrossoverReport


class CrossoverEngine:
    def crossover(self, parent_a: StrategyGenome, parent_b: StrategyGenome, seed: int | None = None) -> tuple[StrategyGenome, CrossoverReport]:
        rng = random.Random(seed) if seed is not None else random
        child_id = f"cx-{parent_a.strategy_id[:8]}-{parent_b.strategy_id[:8]}"
        child = parent_a.model_copy(deep=True)
        child.strategy_id = child_id
        child.parent_ids = [parent_a.strategy_id, parent_b.strategy_id]
        child.generation = max(parent_a.generation, parent_b.generation) + 1
        child.archetype = f"cx:{parent_a.archetype}:{parent_b.archetype}"

        inherited: dict[str, Any] = {}

        child.confidence_threshold, src = self._pick(parent_a.confidence_threshold, parent_b.confidence_threshold, rng)
        inherited["confidence_threshold"] = src

        child.sizing_multiplier, src = self._pick(parent_a.sizing_multiplier, parent_b.sizing_multiplier, rng)
        inherited["sizing_multiplier"] = src

        child.risk_multiplier, src = self._pick(parent_a.risk_multiplier, parent_b.risk_multiplier, rng)
        inherited["risk_multiplier"] = src

        child.consensus_mode, src = self._pick(parent_a.consensus_mode, parent_b.consensus_mode, rng)
        inherited["consensus_mode"] = src

        all_keys = set(parent_a.signal_weights.keys()) | set(parent_b.signal_weights.keys())
        for k in all_keys:
            if rng.random() < 0.5:
                child.signal_weights[k] = parent_a.signal_weights.get(k, 0.5)
                inherited.setdefault("signal_weights", {})[k] = "parent_a"
            else:
                child.signal_weights[k] = parent_b.signal_weights.get(k, 0.5)
                inherited.setdefault("signal_weights", {})[k] = "parent_b"

        report = CrossoverReport(
            child_id=child_id,
            parent_a_id=parent_a.strategy_id,
            parent_b_id=parent_b.strategy_id,
            inherited_traits=inherited,
            crossover_type="uniform",
        )
        return child, report

    def _pick(self, val_a: Any, val_b: Any, rng: random.Random) -> tuple[Any, str]:
        if rng.random() < 0.5:
            return val_a, "parent_a"
        return val_b, "parent_b"


crossover_engine = CrossoverEngine()