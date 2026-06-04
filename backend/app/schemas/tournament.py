from pydantic import BaseModel
from typing import Any


class TournamentRanking(BaseModel):
    strategy: str
    rank: int
    score: float
    percentile: float
    confidence: float
    tier: str
    trend: str = "stable"
    sharpe: float = 0.0
    sortino: float = 0.0
    win_rate: float = 0.0
    expectancy: float = 0.0
    max_drawdown: float = 0.0
    alpha: float = 0.0
    total_trades: int = 0


class StrategyAllocation(BaseModel):
    strategy: str
    allocation_pct: float
    capital_assigned: float
    risk_score: float = 0.0


class AllocationResult(BaseModel):
    mode: str
    allocations: list[StrategyAllocation]
    total_capital: float
    description: str = ""


class SimulatorPoint(BaseModel):
    step: int
    equity: float
    pnl: float
    drawdown: float
    date: str = ""


class StrategyContribution(BaseModel):
    strategy: str
    contribution_pct: float
    total_pnl: float
    trade_count: int


class SimulationResult(BaseModel):
    starting_capital: float
    final_equity: float
    total_return: float
    total_return_pct: float
    cagr: float
    volatility: float
    sharpe: float
    calmar_ratio: float
    profit_factor: float
    recovery_factor: float
    max_drawdown: float
    max_drawdown_pct: float
    equity_curve: list[SimulatorPoint]
    strategy_contributions: list[StrategyContribution]


class PromotionRecommendation(BaseModel):
    strategy: str
    action: str  # promote / demote / hold
    from_tier: str
    to_tier: str
    window: str  # 7d / 30d / lifetime
    reason: str
    score_7d: float = 0.0
    score_30d: float = 0.0
    score_lifetime: float = 0.0


class TournamentWindowMetrics(BaseModel):
    strategy: str
    pnl_7d: float = 0.0
    pnl_30d: float = 0.0
    pnl_lifetime: float = 0.0
    trades_7d: int = 0
    trades_30d: int = 0
    trades_lifetime: int = 0
    win_rate_7d: float = 0.0
    win_rate_30d: float = 0.0
    win_rate_lifetime: float = 0.0
    sharpe_7d: float = 0.0
    sharpe_30d: float = 0.0
    sharpe_lifetime: float = 0.0
