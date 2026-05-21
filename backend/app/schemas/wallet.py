from datetime import datetime

from pydantic import BaseModel, Field


class WalletResponse(BaseModel):
    address: str
    total_trades: int = 0
    total_volume: float = 0
    realized_pnl: float = 0
    win_rate: float | None = None
    win_count: int = 0
    loss_count: int = 0
    current_rank: int | None = None
    tags: list[str] | None = None

    model_config = {"from_attributes": True}


class WalletDetailResponse(WalletResponse):
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    updated_at: datetime | None = None


class WalletScoreResponse(BaseModel):
    id: int
    wallet_address: str
    score_type: str
    score: float
    confidence: float | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    metadata: dict | None = None
    calculated_at: datetime | None = None

    model_config = {"from_attributes": True}
