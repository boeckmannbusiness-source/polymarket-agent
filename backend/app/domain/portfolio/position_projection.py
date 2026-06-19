from decimal import Decimal
from pydantic import BaseModel


class PositionProjection(BaseModel):
    instrument: str
    quantity_before: Decimal
    quantity_after: Decimal
    avg_price_before: Decimal
    avg_price_after: Decimal
    estimated_pnl: Decimal
    estimated_fees: Decimal
