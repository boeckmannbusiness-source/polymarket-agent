from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Fill, ExchangeOrder


class ExecutionMetricsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_trade_metrics(self, trade_id):
        result = await self.db.execute(
            select(
                func.count(Fill.id).label("fill_count"),
                func.sum(Fill.size).label("total_filled"),
                func.avg(Fill.price).label("avg_price"),
                func.sum(Fill.fee).label("total_fees"),
            ).where(Fill.trade_id == trade_id)
        )
        row = result.one()

        result = await self.db.execute(
            select(ExchangeOrder).where(
                ExchangeOrder.trade_id == trade_id,
                ExchangeOrder.status == "submitted",
            )
        )
        pending = result.scalar_one_or_none()

        fill_count = row.fill_count or 0
        total_filled = float(row.total_filled) if row.total_filled else 0.0
        avg_price = float(row.avg_price) if row.avg_price else 0.0
        total_fees = float(row.total_fees) if row.total_fees else 0.0

        result = await self.db.execute(
            select(ExchangeOrder).where(
                ExchangeOrder.trade_id == trade_id,
                ExchangeOrder.status.in_(["filled", "partially_filled"]),
            )
        )
        orders = list(result.scalars().all())
        total_requested = sum(float(o.size) for o in orders) if orders else 0.0

        fill_rate = (total_filled / total_requested * 100) if total_requested > 0 else 0.0

        return {
            "trade_id": str(trade_id),
            "fill_count": fill_count,
            "total_filled": round(total_filled, 8),
            "avg_price": round(avg_price, 8),
            "total_fees": round(total_fees, 8),
            "total_requested": round(total_requested, 8),
            "fill_rate_pct": round(fill_rate, 2),
            "has_pending_order": pending is not None,
        }

    async def get_strategy_metrics(self, agent_id):
        result = await self.db.execute(
            select(
                func.count(Fill.id).label("total_fills"),
                func.sum(Fill.size).label("total_volume"),
                func.sum(Fill.fee).label("total_fees"),
            ).where(Fill.trade.has(agent_id=agent_id))
        )
        row = result.one()

        return {
            "agent_id": agent_id,
            "total_fills": row.total_fills or 0,
            "total_volume": float(row.total_volume) if row.total_volume else 0.0,
            "total_fees": float(row.total_fees) if row.total_fees else 0.0,
        }

    async def get_market_metrics(self, market_id):
        result = await self.db.execute(
            select(
                func.count(Fill.id).label("total_fills"),
                func.sum(Fill.size).label("total_volume"),
                func.avg(Fill.price).label("avg_fill_price"),
            ).where(Fill.market_id == market_id)
        )
        row = result.one()

        return {
            "market_id": str(market_id),
            "total_fills": row.total_fills or 0,
            "total_volume": float(row.total_volume) if row.total_volume else 0.0,
            "avg_fill_price": float(row.avg_fill_price) if row.avg_fill_price else 0.0,
        }

    async def get_all_fills_for_trade(self, trade_id):
        result = await self.db.execute(
            select(Fill).where(Fill.trade_id == trade_id).order_by(Fill.fill_num)
        )
        return list(result.scalars().all())
