from decimal import Decimal
from pydantic import BaseModel
from app.domain.execution.instrument import Instrument


class ExecutionIntent(BaseModel):
    instrument: Instrument
    side: str
    quantity: Decimal
    order_type: str
    limit_price: Decimal | None = None
    slippage_bps: int | None = None
    strategy_id: str | None = None
    metadata: dict | None = None
