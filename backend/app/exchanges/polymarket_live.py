from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExchangeOrder
from app.exchanges.base import BaseExchangeAdapter
from app.exchanges.polymarket_client import PolymarketClobClient
from app.core.logging import logger


class PolymarketLiveAdapter(BaseExchangeAdapter):
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client: PolymarketClobClient | None = None

    async def _get_client(self) -> PolymarketClobClient:
        if self._client is None:
            self._client = PolymarketClobClient()
        return self._client

    async def submit_order(self, exchange_order: ExchangeOrder):
        client = await self._get_client()

        token_id = exchange_order.clob_asset_id
        if not token_id:
            raise ValueError("clob_asset_id is required for live submission")

        try:
            result = await client.post_order(
                token_id=token_id,
                side=exchange_order.side,
                size=exchange_order.size,
                price=exchange_order.price or Decimal("0.5"),
                idempotency_key=exchange_order.idempotency_key,
            )

            clob_order_id = result.get("order_id") or result.get("id")
            if clob_order_id:
                exchange_order.clob_order_id = str(clob_order_id)
            if "signature" in result:
                exchange_order.clob_signature = result["signature"]
            exchange_order.raw_response = result
            exchange_order.status = "submitted"
            exchange_order.submitted_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

            logger.info(
                "live_order_submitted",
                exchange_order_id=str(exchange_order.id),
                clob_order_id=clob_order_id,
            )

        except Exception as e:
            exchange_order.status = "failed"
            exchange_order.last_error = str(e)
            logger.error("live_order_failed", exchange_order_id=str(exchange_order.id), error=str(e))
            raise

        finally:
            await self.db.flush()

    async def cancel_order(self, order_id: str) -> dict:
        client = await self._get_client()
        return await client.cancel_order(order_id)

    async def get_order_status(self, order_id: str) -> dict:
        client = await self._get_client()
        return await client.get_order(order_id)

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
