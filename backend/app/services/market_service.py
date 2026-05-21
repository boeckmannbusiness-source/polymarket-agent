from uuid import UUID

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Market, MarketEvent
from app.core.exceptions import MarketNotFoundError


class MarketService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_markets(
        self,
        skip: int = 0,
        limit: int = 50,
        resolved: bool | None = None,
    ) -> list[Market]:
        query = select(Market)
        if resolved is not None:
            query = query.where(Market.resolved == resolved)
        query = query.order_by(desc(Market.volume)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_market(self, market_id: UUID) -> Market:
        result = await self.db.execute(select(Market).where(Market.id == market_id))
        market = result.scalar_one_or_none()
        if not market:
            raise MarketNotFoundError(f"Market {market_id} not found")
        return market

    async def get_market_by_slug(self, slug: str) -> Market:
        result = await self.db.execute(select(Market).where(Market.slug == slug))
        market = result.scalar_one_or_none()
        if not market:
            raise MarketNotFoundError(f"Market with slug '{slug}' not found")
        return market

    async def get_market_events(
        self,
        market_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[MarketEvent]:
        query = (
            select(MarketEvent)
            .where(MarketEvent.market_id == market_id)
            .order_by(desc(MarketEvent.timestamp))
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def upsert_market(self, condition_id: str, **kwargs) -> Market:
        result = await self.db.execute(select(Market).where(Market.condition_id == condition_id))
        market = result.scalar_one_or_none()
        if market:
            for key, value in kwargs.items():
                if value is not None:
                    setattr(market, key, value)
        else:
            market = Market(condition_id=condition_id, **{k: v for k, v in kwargs.items() if v is not None})
            self.db.add(market)
        await self.db.flush()
        return market
