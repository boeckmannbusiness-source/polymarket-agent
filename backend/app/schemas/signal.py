from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SignalResponse(BaseModel):
    id: UUID
    market_id: UUID | None = None
    signal_type: str
    direction: str
    confidence: float
    implied_probability: float | None = None
    estimated_probability: float | None = None
    reasoning: str | None = None
    source_agent: str | None = None
    source_data: dict | None = None
    generated_at: datetime | None = None
    expired_at: datetime | None = None
    is_active: bool = True

    model_config = {"from_attributes": True}
