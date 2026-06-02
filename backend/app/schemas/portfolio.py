from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class PortfolioSnapshot(BaseModel):
    total_equity: float
    unrealized_pnl: float
    realized_pnl: float
    net_exposure: float
    cash_reserve: float
    open_positions_count: int
    peak_value: float
    drawdown: float
    positions: list["PositionView"]
    top_markets: list["MarketExposureSummary"]
    strategy_breakdown: list["StrategySummary"]
    timestamp: datetime


class PositionView(BaseModel):
    market_id: UUID
    market_slug: str | None = None
    market_title: str | None = None
    outcome: str
    direction: str
    size: float
    entry_price: float
    current_price: float | None = None
    unrealized_pnl: float
    realized_pnl: float
    avg_entry_price: float
    strategy: str | None = None
    opened_at: datetime | None = None
    trade_id: UUID | None = None

    model_config = {"from_attributes": True}


class StrategyPerformance(BaseModel):
    agent_id: str
    strategy_name: str | None = None
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    cumulative_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    avg_trade_duration_hours: float
    max_drawdown: float
    sharpe_ratio: float | None = None
    total_volume: float
    total_fees: float
    pnl_curve: list[PnlPoint]
    created_at: datetime


class PnlPoint(BaseModel):
    timestamp: datetime
    cumulative_pnl: float
    drawdown: float


class StrategySummary(BaseModel):
    agent_id: str
    total_pnl: float
    win_rate: float
    trade_count: int
    total_volume: float


class TradeTimelineEvent(BaseModel):
    event_type: str
    event_label: str
    timestamp: datetime | None = None
    order_id: UUID | None = None
    fill_id: UUID | None = None
    size: float | None = None
    price: float | None = None
    status: str | None = None
    details: dict | None = None


class TradeTimeline(BaseModel):
    trade_id: UUID
    events: list[TradeTimelineEvent]


class MarketExposure(BaseModel):
    total_long_exposure: float
    total_short_exposure: float
    net_exposure: float
    concentration_risk_pct: float
    largest_positions: list[MarketExposureSummary]
    exposure_by_market: list[MarketExposureSummary]
    timestamp: datetime


class MarketExposureSummary(BaseModel):
    market_id: UUID
    market_slug: str | None = None
    market_title: str | None = None
    direction: str
    size: float
    current_price: float | None = None
    exposure_value: float
    pct_of_portfolio: float
    unrealized_pnl: float
