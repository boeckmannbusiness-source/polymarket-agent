from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Position, Market
from app.schemas.portfolio import MarketExposure, MarketExposureSummary


class ExposureService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_market_exposure(self) -> MarketExposure:
        result = await self.db.execute(
            select(Position).where(Position.status == "OPEN")
        )
        positions = list(result.scalars().all())

        total_long = 0.0
        total_short = 0.0
        long_positions = []
        short_positions = []

        for pos in positions:
            exposure = float(pos.size * (pos.current_price or pos.entry_price))
            pnl = float(pos.unrealized_pnl or 0)

            if pos.direction == "BUY":
                total_long += exposure
                long_positions.append((pos, exposure, pnl))
            else:
                total_short += exposure
                short_positions.append((pos, exposure, pnl))

        net_exposure = total_long - total_short
        total = total_long + total_short
        concentration_risk = 0.0

        market_summaries = []
        for pos, exposure, pnl in long_positions + short_positions:
            market = await self._get_market(pos.market_id) if pos.market_id else None
            pct = (exposure / total * 100) if total > 0 else 0.0
            market_summaries.append(MarketExposureSummary(
                market_id=pos.market_id,
                market_slug=market.slug if market else None,
                market_title=market.title if market else None,
                direction=pos.direction,
                size=float(pos.size),
                current_price=float(pos.current_price) if pos.current_price else None,
                exposure_value=round(exposure, 4),
                pct_of_portfolio=round(pct, 2),
                unrealized_pnl=round(pnl, 4),
            ))

        if total > 0 and market_summaries:
            largest = max(m.exposure_value for m in market_summaries)
            concentration_risk = (largest / total) * 100

        largest_positions = sorted(market_summaries, key=lambda m: m.exposure_value, reverse=True)[:5]

        return MarketExposure(
            total_long_exposure=round(total_long, 4),
            total_short_exposure=round(total_short, 4),
            net_exposure=round(net_exposure, 4),
            concentration_risk_pct=round(concentration_risk, 2),
            largest_positions=largest_positions,
            exposure_by_market=market_summaries,
            timestamp=datetime.now(timezone.utc),
        )

    async def _get_market(self, market_id):
        result = await self.db.execute(
            select(Market).where(Market.id == market_id)
        )
        return result.scalar_one_or_none()
