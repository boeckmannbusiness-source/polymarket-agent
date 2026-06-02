from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Fill, Position, Market, Trade
from app.schemas.portfolio import PortfolioSnapshot, PositionView, MarketExposureSummary, StrategySummary


class PortfolioSnapshotService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_portfolio_snapshot(self) -> PortfolioSnapshot:
        result = await self.db.execute(
            select(Position).where(Position.status == "OPEN")
        )
        open_positions = list(result.scalars().all())

        result = await self.db.execute(
            select(Position).where(Position.status == "CLOSED")
        )
        closed_positions = list(result.scalars().all())

        total_unrealized = sum(float(p.unrealized_pnl or 0) for p in open_positions)
        total_realized = sum(float(p.realized_pnl or 0) for p in closed_positions)
        total_exposure = sum(
            float(p.size * (p.current_price or p.entry_price)) for p in open_positions
        )

        peak = max(
            float(p.unrealized_pnl or 0) + float(p.size * (p.current_price or p.entry_price))
            for p in open_positions
        ) if open_positions else 0.0

        portfolio_value = total_exposure + total_unrealized + total_realized
        peak_value = max(portfolio_value, peak)
        drawdown = (peak_value - portfolio_value) / peak_value if peak_value > 0 else 0.0

        position_views = []
        total_by_market: dict = {}
        strategy_agg: dict = {}

        for pos in open_positions:
            market = await self._get_market(pos.market_id) if pos.market_id else None
            pnl = float(pos.unrealized_pnl or 0)
            exposure = float(pos.size * (pos.current_price or pos.entry_price))

            position_views.append(PositionView(
                market_id=pos.market_id,
                market_slug=market.slug if market else None,
                market_title=market.title if market else None,
                outcome="YES",
                direction=pos.direction,
                size=float(pos.size),
                entry_price=float(pos.entry_price),
                current_price=float(pos.current_price) if pos.current_price else None,
                unrealized_pnl=pnl,
                realized_pnl=float(pos.realized_pnl or 0),
                avg_entry_price=float(pos.entry_price),
                strategy=pos.strategy_name,
                opened_at=pos.opened_at,
            ))

            if pos.market_id:
                key = str(pos.market_id)
                if key not in total_by_market:
                    total_by_market[key] = {
                        "market_id": pos.market_id,
                        "market_slug": market.slug if market else None,
                        "market_title": market.title if market else None,
                        "direction": pos.direction,
                        "size": 0.0,
                        "current_price": float(pos.current_price) if pos.current_price else None,
                        "exposure_value": 0.0,
                        "pct_of_portfolio": 0.0,
                        "unrealized_pnl": 0.0,
                    }
                total_by_market[key]["size"] += float(pos.size)
                total_by_market[key]["exposure_value"] += exposure
                total_by_market[key]["unrealized_pnl"] += pnl

            if pos.strategy_name:
                if pos.strategy_name not in strategy_agg:
                    strategy_agg[pos.strategy_name] = {
                        "agent_id": pos.strategy_name,
                        "total_pnl": 0.0,
                        "win_rate": 0.0,
                        "trade_count": 0,
                        "total_volume": 0.0,
                    }
                strategy_agg[pos.strategy_name]["total_pnl"] += pnl + float(pos.realized_pnl or 0)
                strategy_agg[pos.strategy_name]["trade_count"] += 1
                strategy_agg[pos.strategy_name]["total_volume"] += float(pos.size)

        for pos in closed_positions:
            if pos.strategy_name and pos.strategy_name in strategy_agg:
                strategy_agg[pos.strategy_name]["total_pnl"] += float(pos.realized_pnl or 0)
                strategy_agg[pos.strategy_name]["trade_count"] += 1

        top_markets = sorted(
            total_by_market.values(),
            key=lambda m: m["exposure_value"],
            reverse=True,
        )[:10]

        if portfolio_value > 0:
            for m in top_markets:
                m["pct_of_portfolio"] = round((m["exposure_value"] / portfolio_value) * 100, 2)

        strategy_breakdown = [
            StrategySummary(**s) for s in strategy_agg.values()
        ]

        return PortfolioSnapshot(
            total_equity=round(portfolio_value, 4),
            unrealized_pnl=round(total_unrealized, 4),
            realized_pnl=round(total_realized, 4),
            net_exposure=round(total_exposure, 4),
            cash_reserve=0.0,
            open_positions_count=len(open_positions),
            peak_value=round(peak_value, 4),
            drawdown=round(drawdown, 4),
            positions=position_views,
            top_markets=[MarketExposureSummary(**m) for m in top_markets],
            strategy_breakdown=strategy_breakdown,
            timestamp=datetime.now(timezone.utc),
        )

    async def _get_market(self, market_id):
        result = await self.db.execute(
            select(Market).where(Market.id == market_id)
        )
        return result.scalar_one_or_none()
