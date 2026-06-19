from pydantic import BaseModel

from app.domain.markets.instrument_id import InstrumentId
from app.domain.markets.market import Market


class MarketResolution(BaseModel):
    instrument: InstrumentId
    market: Market | None = None
    source: str = "unknown"
    confidence: float = 1.0
