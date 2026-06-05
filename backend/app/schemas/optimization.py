from pydantic import BaseModel
from typing import Any


class OptimizedPortfolioAllocation(BaseModel):
    strategy_id: str
    weight_pct: float = 0.0
    expected_return: float = 0.0
    risk_contribution: float = 0.0
    status: str = "active"


class OptimizationDiagnostics(BaseModel):
    objective_value: float = 0.0
    constraint_violations: list[str] = []
    iterations: int = 0
    convergence_status: str = "success"


class PortfolioOptimizationOutput(BaseModel):
    allocations: list[OptimizedPortfolioAllocation] = []
    diagnostics: OptimizationDiagnostics | None = None
    regime: str = ""
    generated_at: str = ""


class RegimeExpectedReturn(BaseModel):
    strategy_id: str
    expected_return: float = 0.0
    regime_contributions: dict[str, float] = {}
    confidence: float = 0.0


class RegimeExpectedReturnsOutput(BaseModel):
    returns: list[RegimeExpectedReturn] = []
    regime_probabilities: dict[str, float] = {}
    generated_at: str = ""


class RiskModelOutput(BaseModel):
    strategies: list[str] = []
    covariance_matrix: list[list[float]] = []
    correlations: dict[str, dict[str, float]] = {}
    adjustment_factor: float = 1.0
    regime: str = ""
    generated_at: str = ""


class MonteCarloPercentilePath(BaseModel):
    percentile: str  # p5, p25, p50, p75, p95
    equity_curve: list[float] = []
    drawdown_curve: list[float] = []


class MonteCarloPortfolioReport(BaseModel):
    simulation_id: str
    n_paths: int = 1000
    n_steps: int = 252
    expected_drawdown: float = 0.0
    worst_drawdown: float = 0.0
    recovery_time_hours: float = 0.0
    survival_probability: float = 1.0
    sharpe_mean: float = 0.0
    sharpe_std: float = 0.0
    percentile_paths: list[MonteCarloPercentilePath] = []
    executed_at: str = ""


class AllocationLearningUpdate(BaseModel):
    strategy_id: str
    previous_weight: float = 0.0
    adjusted_weight: float = 0.0
    adjustment_reason: str = ""
    learning_signal: float = 0.0
    performance_delta: float = 0.0


class AllocationLearningOutput(BaseModel):
    updates: list[AllocationLearningUpdate] = []
    regime_calibration: dict[str, float] = {}
    risk_penalty_update: dict[str, float] = {}
    generated_at: str = ""


class PortfolioOptimizationReport(BaseModel):
    report_id: str
    generated_at: str = ""
    allocation: PortfolioOptimizationOutput | None = None
    expected_returns: RegimeExpectedReturnsOutput | None = None
    risk_model: RiskModelOutput | None = None
    monte_carlo: MonteCarloPortfolioReport | None = None
    learning: AllocationLearningOutput | None = None
    summary: str = ""
