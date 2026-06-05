from pydantic import BaseModel
from datetime import datetime


class StrategyStableAllocation(BaseModel):
    strategy_id: str
    raw_weight_pct: float = 0.0
    stabilized_weight_pct: float = 0.0
    delta_pct: float = 0.0
    ema_alpha: float = 0.0


class StabilityAdjustmentReport(BaseModel):
    max_delta_weight: float = 0.05
    total_turnover_pct: float = 0.0
    allocations: list[StrategyStableAllocation] = []
    regime_probabilities_stabilized: dict[str, float] = {}
    risk_penalties_stabilized: dict[str, float] = {}
    ema_smoothing_factor: float = 0.3
    applied_at: str = ""


class StabilizedPortfolioState(BaseModel):
    strategy_id: str
    stabilized_weight_pct: float = 0.0
    drift_from_optimal: float = 0.0


class DampenedLearningSignal(BaseModel):
    strategy_id: str
    raw_signal: float = 0.0
    dampened_signal: float = 0.0
    stability_factor: float = 1.0
    effective_learning_rate: float = 0.0
    volatility: float = 0.0


class FeedbackDampeningReport(BaseModel):
    dampened_signals: list[DampenedLearningSignal] = []
    base_learning_rate: float = 0.1
    global_stability_factor: float = 1.0
    regime_instability: float = 0.0
    allocation_variance: float = 0.0
    applied_at: str = ""


class DriftSource(BaseModel):
    source: str = ""
    contribution: float = 0.0


class PortfolioDriftReport(BaseModel):
    overall_drift_score: float = 0.0
    allocation_drift: float = 0.0
    regime_drift: float = 0.0
    risk_drift: float = 0.0
    drift_sources: list[DriftSource] = []
    risk_warnings: list[str] = []
    recommended_actions: list[str] = []
    drift_trend: str = "stable"
    detected_at: str = ""


class StableRegimeState(BaseModel):
    regime: str = ""
    probability: float = 0.0
    persistence_count: int = 0
    inertia: float = 1.0
    transitions_smoothed: bool = False


class RegimeTransitionControlReport(BaseModel):
    regimes: list[StableRegimeState] = []
    transition_matrix: dict[str, dict[str, float]] = {}
    volatility_adjustment: float = 1.0
    applied_at: str = ""


class PortfolioControlReport(BaseModel):
    report_id: str
    generated_at: str = ""
    stability: StabilityAdjustmentReport | None = None
    dampening: FeedbackDampeningReport | None = None
    drift: PortfolioDriftReport | None = None
    regime_transitions: RegimeTransitionControlReport | None = None
    stabilized_state: list[StabilizedPortfolioState] = []
    summary: str = ""
