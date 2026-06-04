from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade, ExchangeOrder, Fill
from app.core.logging import logger


class ExecutionAuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def reconstruct_trade_path(self, trade_id: str) -> dict[str, Any]:
        trade = await self.db.execute(select(Trade).where(Trade.id == trade_id))
        trade = trade.scalar_one_or_none()
        if not trade:
            return {"error": "Trade not found", "trade_id": trade_id}

        orders_result = await self.db.execute(
            select(ExchangeOrder)
            .where(ExchangeOrder.trade_id == trade_id)
            .order_by(ExchangeOrder.order_num)
        )
        orders = list(orders_result.scalars().all())

        fills_result = await self.db.execute(
            select(Fill).where(Fill.trade_id == trade_id).order_by(Fill.filled_at)
        )
        fills = list(fills_result.scalars().all())

        order_ids = [str(o.id) for o in orders]
        fill_order_ids = [str(f.exchange_order_id) for f in fills]
        orphan_orders = [oid for oid in order_ids if oid not in fill_order_ids]

        anomalies = []
        for fill in fills:
            price = float(fill.price) if fill.price else 0
            if price > 0:
                expected = sum(float(f.price or 0) for f in fills if f.id != fill.id) / max(1, len(fills) - 1)
                if expected > 0 and abs(price - expected) / expected > 0.1:
                    anomalies.append({
                        "type": "price_slippage_spike",
                        "fill_id": str(fill.id),
                        "price": price,
                        "expected": round(expected, 4),
                        "slippage_pct": round(abs(price - expected) / expected * 100, 2),
                    })

        return {
            "trade_id": trade_id,
            "trade_status": trade.status,
            "side": trade.side,
            "outcome": trade.outcome,
            "size": float(trade.size),
            "orders": [
                {
                    "id": str(o.id),
                    "order_num": o.order_num,
                    "status": o.status,
                    "side": o.side,
                    "size": float(o.size),
                    "filled_size": float(o.filled_size or 0),
                    "price": float(o.price or 0),
                    "engine_type": o.engine_type,
                    "submitted_at": o.submitted_at.isoformat() if o.submitted_at else None,
                    "idempotency_key": o.idempotency_key,
                }
                for o in orders
            ],
            "fills": [
                {
                    "id": str(f.id),
                    "order_id": str(f.exchange_order_id),
                    "side": f.side,
                    "outcome": f.outcome,
                    "size": float(f.size),
                    "price": float(f.price),
                    "fee": float(f.fee),
                    "filled_at": f.filled_at.isoformat() if f.filled_at else None,
                }
                for f in fills
            ],
            "orphan_orders": orphan_orders,
            "anomalies": anomalies,
            "consistency": {
                "orders_match_fills": len(orphan_orders) == 0,
                "total_filled_size": sum(float(f.size) for f in fills),
                "total_order_size": sum(float(o.size) for o in orders),
                "order_count": len(orders),
                "fill_count": len(fills),
            },
        }

    async def system_audit_summary(self) -> dict[str, Any]:
        total_trades = await self.db.execute(select(func.count(Trade.id)))
        total_trades = total_trades.scalar() or 0

        open_trades = await self.db.execute(select(func.count(Trade.id)).where(Trade.status == "open"))
        open_trades = open_trades.scalar() or 0

        total_orders = await self.db.execute(select(func.count(ExchangeOrder.id)))
        total_orders = total_orders.scalar() or 0

        pending_orders = await self.db.execute(
            select(func.count(ExchangeOrder.id)).where(ExchangeOrder.status == "pending")
        )
        pending_orders = pending_orders.scalar() or 0

        total_fills = await self.db.execute(select(func.count(Fill.id)))
        total_fills = total_fills.scalar() or 0

        return {
            "trades": {"total": total_trades, "open": open_trades},
            "orders": {"total": total_orders, "pending": pending_orders},
            "fills": {"total": total_fills},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def detect_orphan_orders(self) -> list[dict]:
        result = await self.db.execute(
            select(ExchangeOrder).where(ExchangeOrder.status.in_(["pending", "submitted"]))
        )
        pending_orders = list(result.scalars().all())
        orphans = []
        for order in pending_orders:
            fill_check = await self.db.execute(
                select(func.count(Fill.id)).where(Fill.exchange_order_id == order.id)
            )
            fill_count = fill_check.scalar() or 0
            if fill_count == 0 and order.age_seconds and order.age_seconds > 3600:
                orphans.append({
                    "order_id": str(order.id),
                    "trade_id": str(order.trade_id),
                    "status": order.status,
                    "age_seconds": order.age_seconds,
                })
        return orphans

    async def detect_duplicate_fills(self) -> list[dict]:
        result = await self.db.execute(
            select(Fill.exchange_order_id, func.count(Fill.id).label("cnt"))
            .group_by(Fill.exchange_order_id)
            .having(func.count(Fill.id) > 1)
        )
        duplicates = []
        for row in result:
            dup_fills = await self.db.execute(
                select(Fill).where(Fill.exchange_order_id == row.exchange_order_id).order_by(Fill.filled_at)
            )
            fills = list(dup_fills.scalars().all())
            duplicates.append({
                "order_id": str(row.exchange_order_id),
                "fill_count": row.cnt,
                "total_size": sum(float(f.size) for f in fills),
                "fills": [str(f.id) for f in fills],
            })
        return duplicates
