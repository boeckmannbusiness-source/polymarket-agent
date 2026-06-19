from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class FillEvent(BaseModel):
    instruction_index: int
    instruction_type: str
    source_asset: str
    target_asset: str
    amount_in: Decimal
    amount_out: Decimal
    price: Decimal
    fee: Decimal
    slippage_bps: int
    latency_ms: float
    timestamp: datetime
