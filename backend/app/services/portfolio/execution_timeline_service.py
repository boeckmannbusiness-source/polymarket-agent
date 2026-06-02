from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade, ExchangeOrder, Fill
from app.schemas.portfolio import TradeTimeline, TradeTimelineEvent


class ExecutionTimelineService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_trade_timeline(self, trade_id) -> TradeTimeline:
        result = await self.db.execute(
            select(Trade).where(Trade.id == trade_id)
        )
        trade = result.scalar_one_or_none()
        if not trade:
            return TradeTimeline(trade_id=trade_id, events=[])

        events: list[TradeTimelineEvent] = []

        events.append(TradeTimelineEvent(
            event_type="TradeCreated",
            event_label="Trade Created",
            timestamp=trade.created_at,
            status=trade.status,
            details={
                "side": trade.side,
                "outcome": trade.outcome,
                "size": float(trade.size),
                "agent_id": trade.agent_id,
            },
        ))

        result = await self.db.execute(
            select(ExchangeOrder)
            .where(ExchangeOrder.trade_id == trade_id)
            .order_by(ExchangeOrder.order_num)
        )
        orders = list(result.scalars().all())

        for order in orders:
            events.append(TradeTimelineEvent(
                event_type="OrderSubmitted",
                event_label=f"Order #{order.order_num} Submitted",
                timestamp=order.submitted_at or order.created_at,
                order_id=order.id,
                size=float(order.size),
                price=float(order.price) if order.price else None,
                status=order.status,
                details={
                    "engine_type": order.engine_type,
                    "side": order.side,
                    "outcome": order.outcome,
                },
            ))

            result = await self.db.execute(
                select(Fill)
                .where(Fill.exchange_order_id == order.id)
                .order_by(Fill.fill_num)
            )
            fills = list(result.scalars().all())

            for fill in fills:
                events.append(TradeTimelineEvent(
                    event_type="FillEvent",
                    event_label=f"Fill #{fill.fill_num}",
                    timestamp=fill.filled_at,
                    order_id=fill.exchange_order_id,
                    fill_id=fill.id,
                    size=float(fill.size),
                    price=float(fill.price),
                    status="filled",
                    details={
                        "side": fill.side,
                        "outcome": fill.outcome,
                        "fee": float(fill.fee),
                    },
                ))

            final_status = order.status
            if final_status == "filled":
                events.append(TradeTimelineEvent(
                    event_type="OrderFilled",
                    event_label=f"Order #{order.order_num} Fully Filled",
                    timestamp=order.filled_at or order.created_at,
                    order_id=order.id,
                    status="filled",
                ))
            elif final_status == "cancelled":
                events.append(TradeTimelineEvent(
                    event_type="OrderCancelled",
                    event_label=f"Order #{order.order_num} Cancelled",
                    timestamp=order.cancelled_at or order.created_at,
                    order_id=order.id,
                    status="cancelled",
                    details={"last_error": order.last_error} if order.last_error else None,
                ))
            elif final_status == "failed":
                events.append(TradeTimelineEvent(
                    event_type="OrderFailed",
                    event_label=f"Order #{order.order_num} Failed",
                    timestamp=order.created_at,
                    order_id=order.id,
                    status="failed",
                    details={"last_error": order.last_error} if order.last_error else None,
                ))

        events.sort(key=lambda e: (e.timestamp or trade.created_at, str(e.order_id or ""), str(e.fill_id or "")))

        return TradeTimeline(trade_id=trade_id, events=events)
