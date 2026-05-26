from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Market, MarketEvent, MarketStateSnapshot


class MarketEnrichmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def enrich(self, condition_id: str | None) -> dict[str, Any]:
        if not condition_id:
            return {}

        result = await self.db.execute(
            select(Market).where(Market.condition_id == condition_id)
        )
        market = result.scalar_one_or_none()
        if not market:
            return {"condition_id": condition_id}

        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(MarketStateSnapshot)
            .where(MarketStateSnapshot.market_id == market.id)
            .order_by(MarketStateSnapshot.timestamp.desc())
            .limit(1)
        )
        snapshot = result.scalar_one_or_none()

        five_min_ago = now - timedelta(minutes=5)
        vol_result = await self.db.execute(
            select(func.coalesce(func.sum(MarketEvent.size), 0))
            .where(
                MarketEvent.market_id == market.id,
                MarketEvent.timestamp >= five_min_ago,
            )
        )
        volume_5m = float(vol_result.scalar() or 0)

        price_result = await self.db.execute(
            select(MarketEvent.price)
            .where(
                MarketEvent.market_id == market.id,
                MarketEvent.price.isnot(None),
            )
            .order_by(MarketEvent.timestamp.desc())
            .limit(1)
        )
        latest_price_row = price_result.one_or_none()
        current_price = float(latest_price_row[0]) if latest_price_row and latest_price_row[0] else None

        enriched: dict[str, Any] = {
            "condition_id": condition_id,
            "market_id": str(market.id),
        }

        if snapshot:
            if snapshot.momentum is not None:
                enriched["momentum_1h"] = float(snapshot.momentum)
            if snapshot.spread is not None:
                enriched["spread"] = float(snapshot.spread)
            if snapshot.volume_1h is not None:
                enriched["volume_1h"] = float(snapshot.volume_1h)
            if snapshot.volume_acceleration is not None:
                enriched["volume_acceleration"] = float(snapshot.volume_acceleration)
            if snapshot.whale_pressure is not None:
                enriched["whale_pressure"] = float(snapshot.whale_pressure)
            if snapshot.orderbook_imbalance is not None:
                enriched["orderbook_imbalance"] = float(snapshot.orderbook_imbalance)
            if snapshot.regime is not None:
                enriched["regime"] = snapshot.regime
            if snapshot.volatility is not None:
                enriched["volatility"] = float(snapshot.volatility)
            if snapshot.trade_count_1h is not None:
                enriched["trade_count_1h"] = snapshot.trade_count_1h

        if current_price is not None:
            enriched["current_price"] = current_price

        enriched["volume_5m"] = volume_5m

        return enriched
