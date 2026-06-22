from datetime import datetime, timezone
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExchangeOrder, Fill
from app.exchanges.base import BaseExchangeAdapter
from app.domain.execution import ExecutionResult
from app.core.logging import logger


class PaperExchangeAdapter(BaseExchangeAdapter):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_order(self, exchange_order: ExchangeOrder) -> ExecutionResult:
        trade = exchange_order.trade
        base_price = exchange_order.price
        if base_price is None:
            base_price = Decimal("0.5")

        size = exchange_order.size
        eo_id = exchange_order.id
        eo_trade_id = exchange_order.trade_id
        eo_outcome = exchange_order.outcome

        slippage = Decimal("0.001")
        if exchange_order.side == "buy":
            fill_price = base_price * (Decimal("1") + slippage)
        else:
            fill_price = base_price * (Decimal("1") - slippage)

        fee = size * Decimal("0.001")

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

        from app.domain.execution.execution_result import FillInfo as EFillInfo
        return ExecutionResult(
            execution_id=str(eo_id) if eo_id else str(uuid.uuid4()),
            adapter="paper",
            status="filled",
            average_price=fill_price,
            quantity_executed=size,
            fees=fee,
            fills=[EFillInfo(fill_id=str(fill.id), size=size, price=fill_price, fee=fee, timestamp=fill.filled_at)]
        )

    async def cancel_order(self, order_id: str) -> dict:
        return {"status": "cancelled"}

    async def get_order_status(self, order_id: str) -> dict:
        return {"status": "unknown"}
