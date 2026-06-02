import json

from app.core.events import EventBus
from app.core.logging import logger
from app.models import Fill


class EventStreamService:
    async def publish_fill_event(self, fill: Fill) -> None:
        try:
            payload = {
                "fill_id": str(fill.id),
                "exchange_order_id": str(fill.exchange_order_id),
                "trade_id": str(fill.trade_id),
                "market_id": str(fill.market_id),
                "side": fill.side,
                "outcome": fill.outcome,
                "size": float(fill.size),
                "price": float(fill.price),
                "fee": float(fill.fee),
                "filled_at": fill.filled_at.isoformat() if fill.filled_at else None,
            }

            await EventBus.publish(
                "trade:execution",
                "fill.created",
                "event_stream_service",
                payload,
            )

            logger.info(
                "fill_event_published",
                fill_id=str(fill.id),
                trade_id=str(fill.trade_id),
            )

        except Exception as e:
            logger.warning("fill_event_publish_failed", error=str(e))
