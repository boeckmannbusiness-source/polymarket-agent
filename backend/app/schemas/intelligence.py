from pydantic import BaseModel
from typing import Any


class PortfolioIntelligenceReport(BaseModel):
    quality_score: float = 0.0
    diversification_score: float = 0.0
    concentration_score: float = 0.0
    regime_fitness_score: float = 0.0
    strategy_overlap_score: float = 0.0
    capital_efficiency_score: float = 0.0
    generated_at: str = ""


class RegimeAdjustment(BaseModel):
    strategy_id: str
    from_allocation: float = 0.0
    to_allocation: float = 0.0
    delta: float = 0.0
    rationale: str = ""
    confidence: float = 0.0


class RegimeAllocationPlan(BaseModel):
    regime: str = ""
    regime_confidence: float = 0.0
    adjustments: list[RegimeAdjustment] = []
    generated_at: str = ""


class StressTestScenario(BaseModel):
    scenario_id: str
    scenario_type: str = ""  # market_crash|liquidity_collapse|news_shock|strategy_failure|regime_shift|correlation_spike
    parameters: dict[str, Any] = {}


class StressTestResult(BaseModel):
    scenario_id: str
    scenario_type: str = ""
    expected_drawdown: float = 0.0
    recovery_time_hours: float = 0.0
    resilience_score: float = 0.0
    strategy_survivability: dict[str, float] = {}
    executed_at: str = ""


class ResilienceReport(BaseModel):
    concentration_risk: float = 0.0
    dependency_risk: float = 0.0
    single_strategy_exposure: float = 0.0
    single_regime_exposure: float = 0.0
    survivability_score: float = 0.0
    generated_at: str = ""


class CommitteeRecommendation(BaseModel):
    recommendation_type: str = ""  # increase_allocation|retire_strategy|incubate_candidate|reduce_concentration
    target: str = ""
    rationale: str = ""
    supporting_metrics: dict[str, Any] = {}
    confidence: float = 0.0


class InvestmentCommitteeReport(BaseModel):
    report_id: str
    recommendations: list[CommitteeRecommendation] = []
    summary: str = ""
    generated_at: str = ""


class PortfolioReviewReport(BaseModel):
    review_id: str
    generated_at: str = ""
    intelligence: PortfolioIntelligenceReport | None = None
    regime_allocation: RegimeAllocationPlan | None = None
    stress_tests: list[StressTestResult] = []
    resilience: ResilienceReport | None = None
    committee: InvestmentCommitteeReport | None = None
    summary: str = ""
