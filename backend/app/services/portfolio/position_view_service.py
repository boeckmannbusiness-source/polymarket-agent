from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Position, Market
from app.schemas.portfolio import PositionView


class PositionViewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_positions_overview(self) -> list[PositionView]:
        result = await self.db.execute(
            select(Position).order_by(Position.opened_at.desc())
        )
        positions = list(result.scalars().all())

        views = []
        for pos in positions:
            market = await self._get_market(pos.market_id) if pos.market_id else None

            pnl = float(pos.unrealized_pnl or 0) if pos.status == "OPEN" else float(pos.realized_pnl or 0)

            views.append(PositionView(
                market_id=pos.market_id,
                market_slug=market.slug if market else None,
                market_title=market.title if market else None,
                outcome="YES",
                direction=pos.direction,
                size=float(pos.size),
                entry_price=float(pos.entry_price),
                current_price=float(pos.current_price) if pos.current_price else None,
                unrealized_pnl=float(pos.unrealized_pnl or 0) if pos.status == "OPEN" else 0.0,
                realized_pnl=float(pos.realized_pnl or 0),
                avg_entry_price=float(pos.entry_price),
                strategy=pos.strategy_name,
                opened_at=pos.opened_at,
            ))

        return views

    async def _get_market(self, market_id):
        result = await self.db.execute(
            select(Market).where(Market.id == market_id)
        )
        return result.scalar_one_or_none()
