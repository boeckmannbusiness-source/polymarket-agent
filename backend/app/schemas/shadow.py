from pydantic import BaseModel
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
