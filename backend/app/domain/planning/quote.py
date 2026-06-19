from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel
from app.domain.execution.instrument import Instrument


class Quote(BaseModel):
    instrument: Instrument
    amount_in: Decimal
    expected_amount_out: Decimal
    estimated_price: Decimal
    slippage_bps: int
    source: str
    timestamp: datetime | None = None
    source_latency_ms: float | None = None
    price_impact_estimate: float | None = None
    liquidity_depth: Decimal | None = None
    venue_hint: str | None = None
