from pydantic import BaseModel, Field
from datetime import datetime, timezone


class PromotionRecommendation(BaseModel):
    strategy_id: str
    current_tier: str
    recommended_tier: str
    reasons: list[str] = []
    score: float = 0.0
    source: str = ""
    created_at: str = ""


class RetirementRecommendation(BaseModel):
    strategy_id: str
    reason: str
    triggers: list[str] = []
    score: float = 0.0
    created_at: str = ""


class LifecycleDecision(BaseModel):
    strategy_id: str
    decision_type: str  # promoted|demoted|retired|reactivated
    from_tier: str | None = None
    to_tier: str | None = None
    reasons: list[str] = []
    created_at: str = ""


class TierLimits(BaseModel):
    live_max_pct: float = 25.0
    paper_max_pct: float = 10.0
    shadow_max_pct: float = 0.0
    min_allocation_pct: float = 1.0
    max_allocation_pct: float = 25.0


class StrategyAllocation(BaseModel):
    strategy_id: str
    tier: str
    allocation_pct: float = 0.0
    confidence: float = 0.0
    health: float = 0.0
    sharpe: float = 0.0
    rank: int = 0


class CapitalAllocationPlan(BaseModel):
    allocations: list[StrategyAllocation] = []
    total_pct: float = 0.0
    mode: str = "balanced"
    generated_at: str = ""


class GovernanceRecord(BaseModel):
    record_id: str
    strategy_id: str
    decision_type: str
    reasoning: str
    details: dict = {}
    created_at: str = ""


class PortfolioRecommendation(BaseModel):
    active_strategies: list[dict] = []
    retirement_candidates: list[RetirementRecommendation] = []
    promotion_candidates: list[PromotionRecommendation] = []
    allocation_plan: CapitalAllocationPlan | None = None
    generated_at: str = ""
