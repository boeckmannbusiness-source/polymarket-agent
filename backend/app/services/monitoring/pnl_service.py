from decimal import Decimal
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Fill, Position


class PnLService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def compute_unrealized_pnl(self, position: Position, current_price: float) -> float:
        if position.status != "OPEN" or position.size <= 0:
            return 0.0

        price_move = current_price - float(position.entry_price)
        if position.direction == "NO":
            price_move = -price_move
        return price_move * float(position.size)

    async def compute_realized_pnl(self, market_id=None) -> list[dict[str, Any]]:
        query = select(
            Fill.trade_id,
            Fill.market_id,
            Fill.side,
            Fill.size,
            Fill.price,
            Fill.fee,
        ).order_by(Fill.filled_at)

        if market_id:
            query = query.where(Fill.market_id == market_id)

        result = await self.db.execute(query)
        fills = result.all()

        buy_fills: dict[str, list[dict]] = {}
        sell_fills: dict[str, list[dict]] = {}

        for f in fills:
            key = str(f.market_id)
            entry = {
                "trade_id": str(f.trade_id),
                "size": float(f.size),
                "price": float(f.price),
                "fee": float(f.fee),
            }
            if f.side == "buy":
                buy_fills.setdefault(key, []).append(entry)
            else:
                sell_fills.setdefault(key, []).append(entry)

        pnl_results = []
        for market_key in set(list(buy_fills.keys()) + list(sell_fills.keys())):
            buys = buy_fills.get(market_key, [])
            sells = sell_fills.get(market_key, [])
            total_buy_cost = sum(b["size"] * b["price"] for b in buys) + sum(b["fee"] for b in buys)
            total_buy_size = sum(b["size"] for b in buys)
            total_sell_revenue = sum(s["size"] * s["price"] for s in sells) - sum(s["fee"] for s in sells)
            total_sell_size = sum(s["size"] for s in sells)
            realized = total_sell_revenue - (total_buy_cost * (total_sell_size / total_buy_size)) if total_buy_size > 0 else 0.0

            pnl_results.append({
                "market_id": market_key,
                "realized_pnl": round(realized, 8),
                "bought_size": round(total_buy_size, 8),
                "sold_size": round(total_sell_size, 8),
                "buy_cost": round(total_buy_cost, 8),
                "sell_revenue": round(total_sell_revenue, 8),
            })

        return pnl_results

    async def get_portfolio_pnl(self) -> dict[str, Any]:
        result = await self.db.execute(
            select(Position).where(Position.status == "OPEN")
        )
        open_positions = list(result.scalars().all())

        realized_result = await self.compute_realized_pnl()
        total_realized = sum(r["realized_pnl"] for r in realized_result)
        total_unrealized = sum(float(p.unrealized_pnl or 0) for p in open_positions)

        return {
            "total_realized_pnl": round(total_realized, 8),
            "total_unrealized_pnl": round(total_unrealized, 8),
            "total_pnl": round(total_realized + total_unrealized, 8),
            "open_positions": len(open_positions),
        }
