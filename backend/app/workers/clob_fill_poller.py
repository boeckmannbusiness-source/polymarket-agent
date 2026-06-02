import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.core.logging import logger
from app.models import ExchangeOrder
from app.exchanges.polymarket_client import PolymarketClobClient
from app.services.execution.fill_ingestion_service import FillIngestionService


class CLOBFillPoller:
    def __init__(self, poll_interval: int = 30):
        self.poll_interval = poll_interval
        self._running = False
        self._client: PolymarketClobClient | None = None

    async def run(self):
        self._running = True
        logger.info("clob_fill_poller_started", interval=self.poll_interval)

        while self._running:
            try:
                await self._poll_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("clob_fill_poller_error", error=str(e))

            await asyncio.sleep(self.poll_interval)

        if self._client:
            await self._client.close()

    async def _poll_cycle(self):
        async with async_session_factory() as db:
            result = await db.execute(
                select(ExchangeOrder).where(
                    ExchangeOrder.engine_type == "live",
                    ExchangeOrder.clob_order_id.isnot(None),
                    ExchangeOrder.status.in_(["submitted", "partially_filled"]),
                )
            )
            active_orders = list(result.scalars().all())

            if not active_orders:
                return

            if not self._client:
                self._client = PolymarketClobClient()

            ingester = FillIngestionService(db)

            for order in active_orders:
                try:
                    fills = await self._client.get_fills(order_id=order.clob_order_id)
                    if fills:
                        await ingester.ingest_clob_fills(fills)
                        await db.commit()
                except Exception as e:
                    logger.error(
                        "clob_fill_poll_order_error",
                        order_id=str(order.id),
                        clob_order_id=order.clob_order_id,
                        error=str(e),
                    )
                    await db.rollback()

    async def stop(self):
        self._running = False
