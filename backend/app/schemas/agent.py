from pydantic import BaseModel
from typing import Literal


class AgentPortfolioSnapshot(BaseModel):
    total_equity: float
    cash_balance: float
    exposure: float
    pnl_24h: float
    pnl_total: float


class AgentStrategyPerformanceItem(BaseModel):
    name: str
    pnl_24h: float
    pnl_total: float
    win_rate: float | None
    num_trades: int
    sharpe_ratio: float | None


class AgentSignalDistribution(BaseModel):
    long: int
    short: int
    neutral: int


class AgentMarketState(BaseModel):
    active_markets_count: int
    volatility_index: float | None
    liquidity_score: float | None
    signal_distribution: AgentSignalDistribution


class AgentRiskState(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    max_drawdown: float | None
    exposure_utilization_pct: float | None
    active_risk_alerts: list[str]


class AgentFullSnapshot(BaseModel):
    timestamp: str
    portfolio: AgentPortfolioSnapshot
    strategies: list[AgentStrategyPerformanceItem]
    market: AgentMarketState
    risk: AgentRiskState
