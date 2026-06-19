from pydantic import BaseModel

from app.domain.markets.instrument_id import InstrumentId


class Market(BaseModel):
    instrument_id: InstrumentId
    metadata: dict | None = None
    execution_constraints: dict | None = None
