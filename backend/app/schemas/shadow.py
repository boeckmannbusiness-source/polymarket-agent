from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any


class ShadowExecutionResponse(BaseModel):
    id: str
    signal_id: str
    market_id: str
    strategy: str
    direction: str
    outcome: str
    size: float
    entry_price: float
    current_price: float | None = None
    exit_price: float | None = None
    entry_timestamp: str
    exit_timestamp: str | None = None
    realized_pnl: float | None = None
    unrealized_pnl: float | None = None
    status: str
    outcome_resolved: bool = False
    signal_confidence: float = 0.0


class StrategyAnalytics(BaseModel):
    strategy: str
    total_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    win_rate: float = 0.0
    avg_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    average_holding_time_hours: float = 0.0
    total_signals: int = 0
    executed_signals: int = 0
    closed_positions: int = 0
    win_count: int = 0
    loss_count: int = 0


class BenchmarkComparison(BaseModel):
    strategy: str
    alpha: float = 0.0
    excess_return: float = 0.0
    information_ratio: float = 0.0
    buy_hold_yes_return: float = 0.0
    buy_hold_no_return: float = 0.0
    random_entry_return: float = 0.0


class PromotionResult(BaseModel):
    strategy: str
    current_tier: str = "SHADOW"
    recommended_tier: str = "SHADOW"
    confidence_score: float = 0.0
    reasons: list[str] = []
    blockers: list[str] = []


class PromotionThresholds(BaseModel):
    minimum_trades: int = 10
    minimum_win_rate: float = 0.45
    maximum_drawdown: float = 0.3
    minimum_sharpe: float = 0.5
    minimum_expectancy: float = 0.01


class AnalyticsCache(BaseModel):
    data: dict[str, Any]
    cached_at: float


class ScorecardMetrics(BaseModel):
    decision_count: int = 0
    realized_ev: float = 0.0
    expected_ev: float = 0.0
    alpha: float = 0.0
    win_rate: float = 0.0
    brier_score: float = 1.0
    replay_parity: float = 0.0
    rejection_rate: float = 0.0
    calibration_error: float = 0.0
    confidence_drift: float = 0.0


class StrategyScorecard(BaseModel):
    strategy_id: str
    global_metrics: ScorecardMetrics
    rolling_7d: ScorecardMetrics
    rolling_30d: ScorecardMetrics
    generated_at: datetime = Field(default_factory=datetime.now)


class StabilityReceipt(BaseModel):
    strategy_id: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    metric: str
    message: str
    evidence: dict[str, Any]
    detection_time: datetime = Field(default_factory=datetime.now)


class PromotionEvidenceSnapshot(BaseModel):
    strategy_id: str
    decision_count: int
    replay_parity: float
    realized_ev: float
    brier_score: float
    certification_violations: int
    data_origin: str = "synthetic"  # synthetic, shadow, replay, mixed
    decision_ids: list[str] = Field(default_factory=list)
    resolution_range: tuple[datetime | None, datetime | None] = (None, None)
    source_tables: list[str] = Field(default_factory=lambda: ["shadow_decision_log"])
    timestamp: datetime = Field(default_factory=datetime.now)
    snapshot_hash: str | None = None
