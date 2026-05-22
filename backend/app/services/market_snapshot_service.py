from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Market, MarketEvent, MarketStateSnapshot


class MarketStateSnapshotService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def snapshot_market(self, market_id: str) -> MarketStateSnapshot | None:
        result = await self.db.execute(
            select(Market).where(Market.condition_id == market_id)
        )
        market = result.scalar_one_or_none()
        if not market:
            return None

        now = datetime.now(timezone.utc)

        events_1h = await self.db.execute(
            select(func.count(), func.coalesce(func.sum(MarketEvent.size), 0))
            .where(
                MarketEvent.market_id == market.id,
                MarketEvent.timestamp >= now - timedelta(hours=1),
            )
        )
        trade_count_1h, volume_1h = events_1h.one()

        volume_4h_result = await self.db.execute(
            select(func.coalesce(func.sum(MarketEvent.size), 0))
            .where(
                MarketEvent.market_id == market.id,
                MarketEvent.timestamp.between(now - timedelta(hours=4), now - timedelta(hours=1)),
            )
        )
        volume_4h_prior = volume_4h_result.scalar() or 0

        volume_acceleration = None
        if volume_4h_prior > 0:
            volume_acceleration = (float(volume_1h) - float(volume_4h_prior) / 3) / (float(volume_4h_prior) / 3)

        prices_1h = await self.db.execute(
            select(MarketEvent.price)
            .where(
                MarketEvent.market_id == market.id,
                MarketEvent.timestamp >= now - timedelta(hours=1),
                MarketEvent.price.isnot(None),
            )
            .order_by(MarketEvent.timestamp)
        )
        prices = [float(r[0]) for r in prices_1h.all() if r[0] is not None]
        volatility = None
        momentum = None
        if len(prices) > 1:
            mean_price = sum(prices) / len(prices)
            variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
            volatility = variance ** 0.5
            momentum = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0

        spread = None
        if market.liquidity:
            spread = 1.0 / float(market.liquidity) if float(market.liquidity) > 0 else None

        whale_events = await self.db.execute(
            select(
                func.coalesce(func.sum(MarketEvent.size).filter(MarketEvent.side == "buy"), 0),
                func.coalesce(func.sum(MarketEvent.size).filter(MarketEvent.side == "sell"), 0),
            )
            .where(
                MarketEvent.market_id == market.id,
                MarketEvent.timestamp >= now - timedelta(hours=1),
                MarketEvent.size >= 500,
            )
        )
        whale_buy, whale_sell = whale_events.one()
        total_whale = float(whale_buy) + float(whale_sell)
        whale_pressure = (float(whale_buy) - float(whale_sell)) / total_whale if total_whale > 0 else None

        orderbook_imbalance = None
        if whale_buy or whale_sell:
            orderbook_imbalance = (float(whale_buy) - float(whale_sell)) / (float(whale_buy) + float(whale_sell)) if (float(whale_buy) + float(whale_sell)) > 0 else 0

        regime = self._classify_regime(volatility, momentum, spread, volume_1h)

        snapshot = MarketStateSnapshot(
            market_id=market.id,
            condition_id=market.condition_id,
            spread=spread,
            liquidity=float(market.liquidity) if market.liquidity else None,
            orderbook_imbalance=orderbook_imbalance,
            volatility=volatility,
            volume_acceleration=volume_acceleration,
            whale_pressure=whale_pressure,
            regime=regime,
            momentum=momentum,
            trade_count_1h=int(trade_count_1h) if trade_count_1h else None,
            volume_1h=float(volume_1h) if volume_1h else None,
            timestamp=now,
        )
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def snapshot_all_active_markets(self) -> list[MarketStateSnapshot]:
        result = await self.db.execute(
            select(Market).where(Market.resolved == False)
        )
        markets = list(result.scalars().all())
        snapshots = []
        for market in markets:
            try:
                snap = await self.snapshot_market(market.condition_id)
                if snap:
                    snapshots.append(snap)
            except Exception:
                continue
        return snapshots

    def _classify_regime(self, volatility: float | None, momentum: float | None,
                         spread: float | None, volume_1h) -> str:
        if spread and spread > 0.05:
            return "illiquid"
        if volatility and volatility > 0.1:
            return "high_volatility"
        if volatility and volatility < 0.01:
            return "low_volatility"
        if momentum and abs(momentum) > 0.05:
            return "momentum"
        if momentum and abs(momentum) < 0.005:
            return "mean_reverting"
        return "normal"
