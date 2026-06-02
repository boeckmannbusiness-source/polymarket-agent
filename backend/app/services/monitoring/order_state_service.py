from decimal import Decimal
from datetime import datetime, timezone
from typing import Any
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExchangeOrder, Fill


@dataclass
class OrderStateView:
    order_id: str
    trade_id: str
    engine_type: str
    status: str
    filled_pct: float
    side: str
    outcome: str
    size: float
    filled_size: float
    avg_price: float
    retry_count: int
    last_fill_time: str | None = None
    drift_flag: bool = False
    submitted_at: str | None = None
    created_at: str | None = None
    last_error: str | None = None


class OrderStateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_order_view(self, order_id) -> OrderStateView | None:
        result = await self.db.execute(
            select(ExchangeOrder).where(ExchangeOrder.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            return None
        return await self._build_view(order)

    async def get_trade_orders(self, trade_id) -> list[OrderStateView]:
        result = await self.db.execute(
            select(ExchangeOrder)
            .where(ExchangeOrder.trade_id == trade_id)
            .order_by(ExchangeOrder.order_num)
        )
        orders = list(result.scalars().all())
        return [await self._build_view(o) for o in orders]

    async def get_active_orders(self, engine_type: str | None = None) -> list[OrderStateView]:
        query = select(ExchangeOrder).where(
            ExchangeOrder.status.in_(["pending", "submitted", "partially_filled"])
        )
        if engine_type:
            query = query.where(ExchangeOrder.engine_type == engine_type)
        query = query.order_by(ExchangeOrder.created_at.desc())
        result = await self.db.execute(query)
        orders = list(result.scalars().all())
        return [await self._build_view(o) for o in orders]

    async def _build_view(self, order: ExchangeOrder) -> OrderStateView:
        result = await self.db.execute(
            select(Fill).where(
                Fill.exchange_order_id == order.id
            ).order_by(Fill.filled_at.desc()).limit(1)
        )
        last_fill = result.scalar_one_or_none()

        total_size = float(order.size) if order.size else 0.0
        filled_size = float(order.filled_size) if order.filled_size else 0.0
        filled_pct = (filled_size / total_size * 100) if total_size > 0 else 0.0

        return OrderStateView(
            order_id=str(order.id),
            trade_id=str(order.trade_id),
            engine_type=order.engine_type,
            status=order.status,
            filled_pct=round(filled_pct, 2),
            side=order.side,
            outcome=order.outcome,
            size=total_size,
            filled_size=filled_size,
            avg_price=float(order.filled_price) if order.filled_price else 0.0,
            retry_count=order.retry_count or 0,
            last_fill_time=last_fill.filled_at.isoformat() if last_fill and last_fill.filled_at else None,
            submitted_at=order.submitted_at.isoformat() if order.submitted_at else None,
            created_at=order.created_at.isoformat() if order.created_at else None,
            last_error=order.last_error,
        )
