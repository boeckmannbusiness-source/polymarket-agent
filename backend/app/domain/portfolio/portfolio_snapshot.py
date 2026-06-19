from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class PortfolioSnapshot(BaseModel):
    portfolio_id: str
    timestamp: datetime
    positions: dict[str, Decimal]  # asset -> quantity
    cash_balance: Decimal
    exposure: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    metadata: dict | None = None
