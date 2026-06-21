from datetime import datetime, timezone
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExchangeOrder, Fill
from app.exchanges.base import BaseExchangeAdapter
from app.domain.execution import ExecutionIntent, ExecutionResult
from app.core.logging import logger


class PaperExchangeAdapter(BaseExchangeAdapter):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_order(self, exchange_order: ExchangeOrder | ExecutionIntent):
        if isinstance(exchange_order, ExecutionIntent) and not hasattr(exchange_order, "compat_trade"):
            return ExecutionResult(
                execution_id=str(uuid.uuid4()),
                adapter="paper",
                status="filled",
                quantity_executed=exchange_order.quantity,
                average_price=exchange_order.limit_price or Decimal("0.5"),
            )

        # Legacy compatibility mapping
        trade = getattr(exchange_order, "compat_trade", getattr(exchange_order, "trade", None))
        base_price = getattr(exchange_order, "compat_price", getattr(exchange_order, "price", None))
        if base_price is None:
            base_price = Decimal("0.5")

        size = getattr(exchange_order, "compat_size", getattr(exchange_order, "size", Decimal("0")))
        eo_id = getattr(exchange_order, "compat_id", getattr(exchange_order, "id", None))
        eo_trade_id = getattr(exchange_order, "compat_trade_id", getattr(exchange_order, "trade_id", None))
        eo_outcome = getattr(exchange_order, "compat_outcome", getattr(exchange_order, "outcome", None))

        slippage = Decimal("0.001")
        if exchange_order.side == "buy":
            fill_price = base_price * (Decimal("1") + slippage)
        else:
            fill_price = base_price * (Decimal("1") - slippage)

        fee = size * Decimal("0.001")

        if not isinstance(exchange_order, ExecutionIntent):
            exchange_order.status = "filled"
            exchange_order.filled_size = size
        exchange_order.filled_price = fill_price
        exchange_order.fee = fee
        exchange_order.slippage = slippage
        exchange_order.filled_at = datetime.now(timezone.utc)

        fill = Fill(
            exchange_order_id=eo_id,
            trade_id=eo_trade_id,
            market_id=trade.market_id if trade else None,
            fill_num=1,
            side=exchange_order.side,
            outcome=eo_outcome,
            size=size,
            price=fill_price,
            fee=fee,
            filled_at=datetime.now(timezone.utc),
        )
        self.db.add(fill)
        await self.db.flush()

        from app.services.execution.fill_handler import FillHandler
        handler = FillHandler(self.db)
        await handler.process_fill(fill)

        logger.info(
            "paper_order_filled",
            exchange_order_id=str(eo_id),
            trade_id=str(eo_trade_id),
            side=exchange_order.side,
            outcome=eo_outcome,
            size=size,
            price=fill_price,
            slippage=slippage,
            fee=fee,
        )

        return fill

    async def cancel_order(self, order_id: str) -> dict:
        return {"status": "cancelled"}

    async def get_order_status(self, order_id: str) -> dict:
        return {"status": "unknown"}
