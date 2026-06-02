from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExchangeOrder, Fill
from app.exchanges.polymarket_client import PolymarketClobClient
from app.config import settings
from app.core.logging import logger


class ReconciliationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client: PolymarketClobClient | None = None

    async def _get_client(self) -> PolymarketClobClient:
        if self._client is None:
            self._client = PolymarketClobClient()
        return self._client

    async def reconcile_order(self, exchange_order: ExchangeOrder):
        if not exchange_order.clob_order_id:
            logger.debug("reconcile_skip_no_clob_id", order_id=str(exchange_order.id))
            return

        client = await self._get_client()

        try:
            clob_state = await client.get_order(exchange_order.clob_order_id)
        except Exception as e:
            logger.warning("reconcile_fetch_failed", order_id=str(exchange_order.id), error=str(e))
            return

        clob_status = clob_state.get("status", "").lower() if clob_state else ""
        clob_filled_size = Decimal(str(clob_state.get("filledSize", 0) or 0))
        clob_avg_price = Decimal(str(clob_state.get("avgFillPrice", 0) or 0))

        if clob_status != exchange_order.status:
            logger.info(
                "reconcile_status_drift",
                order_id=str(exchange_order.id),
                db_status=exchange_order.status,
                clob_status=clob_status,
            )
            if clob_status in ("filled", "cancelled", "failed"):
                exchange_order.status = clob_status

        if clob_filled_size > (exchange_order.filled_size or Decimal("0")):
            result = await self.db.execute(
                select(Fill)
                .where(Fill.exchange_order_id == exchange_order.id)
                .order_by(Fill.fill_num.desc())
                .limit(1)
            )
            last_fill = result.scalar_one_or_none()
            fill_num = (last_fill.fill_num + 1) if last_fill else 1

            missing_size = clob_filled_size - (exchange_order.filled_size or Decimal("0"))
            fill = Fill(
                exchange_order_id=exchange_order.id,
                trade_id=exchange_order.trade_id,
                market_id=exchange_order.trade.market_id,
                fill_num=fill_num,
                side=exchange_order.side,
                outcome=exchange_order.outcome,
                size=missing_size,
                price=clob_avg_price,
                fee=Decimal("0"),
                filled_at=datetime.now(timezone.utc),
            )
            self.db.add(fill)

            exchange_order.filled_size = clob_filled_size
            exchange_order.filled_price = clob_avg_price
            exchange_order.status = clob_status
            exchange_order.filled_at = fill.filled_at

            from app.services.execution.fill_handler import FillHandler
            handler = FillHandler(self.db)
            await handler.process_fill(fill)

            logger.info(
                "reconcile_missing_fills_restored",
                order_id=str(exchange_order.id),
                missing_size=missing_size,
            )

        await self.db.flush()

    async def reconcile_all_submitted(self):
        result = await self.db.execute(
            select(ExchangeOrder).where(
                ExchangeOrder.engine_type == "live",
                ExchangeOrder.clob_order_id.isnot(None),
            )
        )
        orders = list(result.scalars().all())
        for order in orders:
            try:
                await self.reconcile_order(order)
            except Exception as e:
                logger.error(
                    "reconcile_order_error",
                    order_id=str(order.id),
                    error=str(e),
                )

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
