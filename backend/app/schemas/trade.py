from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TradeCreateRequest(BaseModel):
    market_id: UUID
    signal_id: UUID | None = None
    side: str = Field(..., pattern="^(buy|sell)$")
    outcome: str
    order_type: str = Field(default="market", pattern="^(market|limit)$")
    size: float = Field(..., gt=0)
    confidence: float | None = 1.0
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    reason: str | None = None
    agent_id: str | None = None
    correlation_id: str | None = None


class TradeResponse(BaseModel):
    id: UUID
    market_id: UUID | None = None
    signal_id: UUID | None = None
    trade_type: str
    status: str
    side: str
    outcome: str
    order_type: str
    size: float
    price: float | None = None
    filled_size: float = 0
    filled_price: float | None = None
    slippage: float | None = None
    pnl: float | None = None
    pnl_percent: float | None = None
    fee: float | None = None
    entry_timestamp: datetime | None = None
    exit_timestamp: datetime | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    reason: str | None = None
    agent_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
