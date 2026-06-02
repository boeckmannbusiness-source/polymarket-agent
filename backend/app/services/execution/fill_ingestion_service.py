from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Fill, ExchangeOrder, Trade
from app.services.execution.fill_handler import FillHandler
from app.core.logging import logger


class FillIngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ingest_clob_fills(self, clob_events: list[dict]):
        for event in clob_events:
            await self._ingest_single(event)

    async def _ingest_single(self, event: dict):
        clob_fill_id = event.get("id") or event.get("fill_id") or event.get("trade_id")
        if not clob_fill_id:
            logger.warning("clob_fill_missing_id", event=event)
            return

        existing = await self.db.execute(
            select(Fill).where(Fill.clob_fill_id == clob_fill_id)
        )
        if existing.scalar_one_or_none():
            logger.debug("clob_fill_already_ingested", clob_fill_id=clob_fill_id)
            return

        clob_order_id = event.get("order_id") or event.get("orderId")
        if not clob_order_id:
            logger.warning("clob_fill_missing_order_id", clob_fill_id=clob_fill_id)
            return

        result = await self.db.execute(
            select(ExchangeOrder).where(ExchangeOrder.clob_order_id == clob_order_id)
        )
        exchange_order = result.scalar_one_or_none()
        if not exchange_order:
            logger.warning("clob_fill_unknown_order", clob_order_id=clob_order_id)
            return

        trade_id = exchange_order.trade_id
        market_id = event.get("market_id") or str(exchange_order.trade.market_id) if exchange_order.trade else None

        side = (event.get("side") or exchange_order.side).lower()
        outcome = event.get("outcome") or exchange_order.outcome
        size = Decimal(str(event.get("size", 0)))
        price = Decimal(str(event.get("price", 0)))
        fee = Decimal(str(event.get("fee", 0)))
        filled_at_str = event.get("timestamp") or event.get("created_at") or event.get("fill_time")
        if filled_at_str:
            try:
                filled_at = datetime.fromisoformat(filled_at_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                filled_at = datetime.now(timezone.utc)
        else:
            filled_at = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(Fill)
            .where(Fill.exchange_order_id == exchange_order.id)
            .order_by(Fill.fill_num.desc())
            .limit(1)
        )
        last_fill = result.scalar_one_or_none()
        fill_num = (last_fill.fill_num + 1) if last_fill else 1

        fill = Fill(
            exchange_order_id=exchange_order.id,
            trade_id=trade_id,
            market_id=exchange_order.trade.market_id,
            fill_num=fill_num,
            clob_fill_id=clob_fill_id,
            transaction_hash=event.get("transaction_hash") or event.get("tx_hash"),
            side=side,
            outcome=outcome or exchange_order.outcome,
            size=size,
            price=price,
            fee=fee,
            filled_at=filled_at,
        )
        self.db.add(fill)

        exchange_order.filled_size = (exchange_order.filled_size or Decimal("0")) + size
        exchange_order.filled_price = price
        exchange_order.fee = (exchange_order.fee or Decimal("0")) + fee
        if exchange_order.filled_size >= exchange_order.size:
            exchange_order.status = "filled"
        else:
            exchange_order.status = "partially_filled"
        exchange_order.filled_at = filled_at

        await self.db.flush()

        handler = FillHandler(self.db)
        await handler.process_fill(fill)

        logger.info(
            "clob_fill_ingested",
            clob_fill_id=clob_fill_id,
            exchange_order_id=str(exchange_order.id),
            size=size,
            price=price,
        )
