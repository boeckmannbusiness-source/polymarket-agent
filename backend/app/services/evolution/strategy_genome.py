import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.evolution import StrategyGenome

DEFAULT_WEIGHTS = {
    "sharpe": 1.0,
    "sortino": 0.8,
    "alpha": 0.6,
    "drawdown": 0.7,
    "win_rate": 0.5,
    "profit_factor": 0.4,
}


class StrategyGenomeService:
    def create(
        self,
        archetype: str = "exploration",
        parent_ids: list[str] | None = None,
        generation: int = 0,
        signal_weights: dict[str, float] | None = None,
        confidence_threshold: float | None = None,
        sizing_multiplier: float | None = None,
        risk_multiplier: float | None = None,
        consensus_mode: str = "majority",
    ) -> StrategyGenome:
        return StrategyGenome(
            strategy_id=str(uuid.uuid4())[:16],
            parent_ids=parent_ids or [],
            generation=generation,
            archetype=archetype,
            signal_weights=signal_weights or dict(DEFAULT_WEIGHTS),
            confidence_threshold=confidence_threshold if confidence_threshold is not None else 0.5,
            sizing_multiplier=sizing_multiplier if sizing_multiplier is not None else 1.0,
            risk_multiplier=risk_multiplier if risk_multiplier is not None else 1.0,
            consensus_mode=consensus_mode,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def clone_from(self, genome: StrategyGenome, new_id: str | None = None) -> StrategyGenome:
        return StrategyGenome(
            strategy_id=new_id or str(uuid.uuid4())[:16],
            parent_ids=genome.parent_ids + [genome.strategy_id],
            generation=genome.generation + 1,
            archetype=genome.archetype,
            signal_weights=dict(genome.signal_weights),
            confidence_threshold=genome.confidence_threshold,
            sizing_multiplier=genome.sizing_multiplier,
            risk_multiplier=genome.risk_multiplier,
            consensus_mode=genome.consensus_mode,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self, genome: StrategyGenome) -> dict[str, Any]:
        return genome.model_dump()

    def from_dict(self, data: dict[str, Any]) -> StrategyGenome:
        return StrategyGenome(**data)


genome_service = StrategyGenomeService()