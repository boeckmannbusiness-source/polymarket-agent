from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MarketResponse(BaseModel):
    id: UUID
    condition_id: str
    slug: str | None = None
    title: str | None = None
    volume: float | None = None
    liquidity: float | None = None
    resolved: bool = False
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class MarketDetailResponse(MarketResponse):
    description: str | None = None
    outcomes: dict | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    clob_token_ids: list[str] | None = None
    resolution: str | None = None
    resolution_source: str | None = None
    updated_at: datetime | None = None


class MarketEventResponse(BaseModel):
    id: int
    market_id: UUID | None = None
    event_type: str
    event_data: dict
    block_number: int | None = None
    transaction_hash: str | None = None
    maker_address: str | None = None
    taker_address: str | None = None
    outcome: str | None = None
    size: float | None = None
    price: float | None = None
    timestamp: datetime
    ingested_at: datetime | None = None

    model_config = {"from_attributes": True}
