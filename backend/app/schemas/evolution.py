from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Any


class StrategyGenome(BaseModel):
    strategy_id: str
    parent_ids: list[str] = []
    generation: int = 0
    archetype: str = "exploration"
    signal_weights: dict[str, float] = {}
    confidence_threshold: float = 0.5
    sizing_multiplier: float = 1.0
    risk_multiplier: float = 1.0
    consensus_mode: str = "majority"
    created_at: str = ""


class FitnessScore(BaseModel):
    strategy_id: str
    sharpe_score: float = 0.0
    sortino_score: float = 0.0
    alpha_score: float = 0.0
    drawdown_score: float = 0.0
    confidence_score: float = 0.0
    health_score: float = 0.0
    promotion_score: float = 0.0
    composite_fitness: float = 0.0
    computed_at: str = ""


class Candidate(BaseModel):
    candidate_id: str
    genome: StrategyGenome | None = None
    status: str = "EXPERIMENTAL"  # EXPERIMENTAL|SHADOW|PAPER|LIVE|RETIRED
    created_at: str = ""
    updated_at: str = ""
    fitness: FitnessScore | None = None


class EvolutionRun(BaseModel):
    run_id: str
    started_at: str = ""
    completed_at: str = ""
    candidates_created: int = 0
    mutations_performed: int = 0
    crossovers_performed: int = 0
    champions_used: list[str] = []
    status: str = "completed"


class CrossoverReport(BaseModel):
    child_id: str
    parent_a_id: str
    parent_b_id: str
    inherited_traits: dict[str, Any] = {}
    crossover_type: str = "uniform"


class PopulationEntry(BaseModel):
    strategy_id: str
    generation: int
    archetype: str
    status: str = "active"  # active|retired
    fitness: float = 0.0
    created_at: str = ""
    retired_at: str | None = None


class LineageNode(BaseModel):
    strategy_id: str
    generation: int
    parent_ids: list[str] = []
    child_ids: list[str] = []
    archetype: str
    status: str
    fitness: float = 0.0