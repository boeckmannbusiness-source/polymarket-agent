from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExchangeOrder, Fill
from app.exchanges.base import BaseExchangeAdapter
from app.core.logging import logger


class PaperExchangeAdapter(BaseExchangeAdapter):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_order(self, exchange_order: ExchangeOrder):
        trade = exchange_order.trade

        slippage = Decimal("0.001")
        base_price = exchange_order.price if exchange_order.price is not None else Decimal("0.5")
        if exchange_order.side == "buy":
            fill_price = base_price * (Decimal("1") + slippage)
        else:
            fill_price = base_price * (Decimal("1") - slippage)

        fee = exchange_order.size * Decimal("0.001")

        exchange_order.status = "filled"
        exchange_order.filled_size = exchange_order.size
        exchange_order.filled_price = fill_price
        exchange_order.fee = fee
        exchange_order.slippage = slippage
        exchange_order.filled_at = datetime.now(timezone.utc)

        fill = Fill(
            exchange_order_id=exchange_order.id,
            trade_id=exchange_order.trade_id,
            market_id=trade.market_id,
            fill_num=1,
            side=exchange_order.side,
            outcome=exchange_order.outcome,
            size=exchange_order.size,
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
            exchange_order_id=str(exchange_order.id),
            trade_id=str(exchange_order.trade_id),
            side=exchange_order.side,
            outcome=exchange_order.outcome,
            size=exchange_order.size,
            price=fill_price,
            slippage=slippage,
            fee=fee,
        )

        return fill

    async def cancel_order(self, order_id: str) -> dict:
        return {"status": "cancelled"}

    async def get_order_status(self, order_id: str) -> dict:
        return {"status": "unknown"}
