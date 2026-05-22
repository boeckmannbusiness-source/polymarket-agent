from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class StructuredSignal(BaseModel):
    strategy: str = Field(..., description="Name of the strategy that generated this signal")
    signal: str = Field(..., pattern="^(BUY_YES|BUY_NO|NEUTRAL)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    market_id: str | None = None
    market_condition_id: str | None = None
    reason: str = Field(..., min_length=1)
    risk_score: float = Field(default=0.5, ge=0.0, le=1.0)
    time_horizon: str = Field(default="medium", pattern="^(short|medium|long)$")
    market_regime: str | None = Field(default=None, pattern="^(high_volatility|low_volatility|momentum|mean_reverting|illiquid|normal)$")
    strategy_version: str = Field(default="1.0.0")
    feature_values: dict | None = None
    generated_at: datetime = Field(default_factory=datetime.now)
