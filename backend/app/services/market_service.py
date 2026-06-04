from uuid import UUID

from sqlalchemy import select, func, desc
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
        clob = kwargs.get("clob_token_ids")
        if clob is not None:
            if isinstance(clob, str):
                import json as _json
                try:
                    kwargs["clob_token_ids"] = [str(t) for t in _json.loads(clob)]
                except (_json.JSONDecodeError, TypeError):
                    kwargs["clob_token_ids"] = [clob]
            elif isinstance(clob, list):
                kwargs["clob_token_ids"] = [str(t) for t in clob if t]

        insert_values = {"condition_id": condition_id}
        for key, value in kwargs.items():
            if value is not None:
                insert_values[key] = value

        stmt = pg_insert(Market).values(**insert_values)
        update_dict = {k: stmt.excluded[k] for k in insert_values if k not in ("condition_id", "id", "created_at")}
        if update_dict:
            stmt = stmt.on_conflict_do_update(
                index_elements=[Market.condition_id],
                set_=update_dict,
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=[Market.condition_id])

        await self.db.execute(stmt)
        await self.db.flush()

        result = await self.db.execute(select(Market).where(Market.condition_id == condition_id))
        return result.scalar_one()
