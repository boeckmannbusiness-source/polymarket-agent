from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict
from app.domain.execution.instrument import Instrument


class ExecutionIntent(BaseModel):
    model_config = ConfigDict(extra="allow")

    instrument: Instrument
    side: str
    quantity: Decimal
    order_type: str
    limit_price: Decimal | None = None
    slippage_bps: int | None = None
    strategy_id: str | None = None
    metadata: dict | None = None

    # Legacy Compatibility Layer (Pre-Sprint 2.0)
    # MUST use compat_ prefix. Forbidden: compat_outcome, compat_market_id, compat_clob_*
    compat_trade: Any = None
    compat_price: Decimal | None = None
    compat_size: Decimal | None = None
    compat_id: Any = None
    compat_trade_id: Any = None
    compat_outcome: str | None = None
