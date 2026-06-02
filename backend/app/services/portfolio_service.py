import math
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Position, PortfolioSnapshot, MarketCorrelation, Market, SignalOutcome, PortfolioAuditLog
from app.models.fill import Fill


class PortfolioService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_from_fill(self, fill: Fill):
        from sqlalchemy import select

        direction = fill.side.upper()

        result = await self.db.execute(
            select(Position).where(
                Position.market_id == fill.market_id,
                Position.status == "OPEN",
            ).limit(1)
        )
        pos = result.scalar_one_or_none()

        if not pos:
            pos = Position(
                market_id=fill.market_id,
                direction=direction,
                size=float(fill.size),
                entry_price=float(fill.price),
                current_price=float(fill.price),
                status="OPEN",
                opened_at=fill.filled_at,
            )
            self.db.add(pos)
        else:
            if direction == pos.direction:
                total_cost = float(pos.size) * float(pos.entry_price) + float(fill.size) * float(fill.price)
                new_size = float(pos.size) + float(fill.size)
                pos.entry_price = total_cost / new_size if new_size > 0 else pos.entry_price
                pos.size = new_size
            else:
                new_size = float(pos.size) - float(fill.size)
                if new_size <= 0:
                    if pos.direction == "BUY":
                        pos.realized_pnl = (float(fill.price) - float(pos.entry_price)) * float(pos.size)
                    else:
                        pos.realized_pnl = (float(pos.entry_price) - float(fill.price)) * float(pos.size)
                    pos.status = "CLOSED"
                    pos.size = 0
                    pos.closed_at = fill.filled_at
                else:
                    pos.size = new_size

            pos.current_price = float(fill.price)

        await self.db.flush()

    async def open_position(
        self,
        market_condition_id: str,
        direction: str,
        size: float,
        entry_price: float,
        strategy_name: str | None = None,
        signal_id: str | None = None,
    ) -> Position:
        result = await self.db.execute(
            select(Market).where(Market.condition_id == market_condition_id)
        )
        market = result.scalar_one_or_none()

        pos = Position(
            market_id=market.id if market else None,
            market_condition_id=market_condition_id,
            direction=direction.upper(),
            size=size,
            entry_price=entry_price,
            current_price=entry_price,
            status="OPEN",
            strategy_name=strategy_name,
            signal_id=uuid.UUID(signal_id) if signal_id else None,
            opened_at=datetime.now(timezone.utc),
        )
        self.db.add(pos)
        await self.db.flush()

        audit = PortfolioAuditLog(
            event_type="POSITION_OPEN",
            delta_cash=None,
            delta_exposure=size * entry_price,
            reference_id=pos.id,
            description=f"OPEN {direction} {size}@{entry_price} market={market_condition_id}",
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(audit)
        await self.db.flush()
        return pos

    async def close_position(self, position_id: uuid.UUID, exit_price: float) -> Position | None:
        result = await self.db.execute(select(Position).where(Position.id == position_id))
        pos = result.scalar_one_or_none()
        if not pos or pos.status == "CLOSED":
            return None

        price_move = exit_price - float(pos.entry_price)
        if pos.direction == "NO":
            price_move = -price_move

        pos.realized_pnl = price_move * float(pos.size)
        pos.current_price = exit_price
        pos.unrealized_pnl = 0.0
        pos.status = "CLOSED"
        pos.closed_at = datetime.now(timezone.utc)
        await self.db.flush()

        audit = PortfolioAuditLog(
            event_type="POSITION_CLOSE",
            delta_cash=float(pos.realized_pnl or 0),
            delta_exposure=-float(pos.size * pos.entry_price),
            reference_id=pos.id,
            description=f"CLOSE {pos.direction} {float(pos.size)}@{exit_price} pnl={float(pos.realized_pnl or 0):+.2f}",
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(audit)
        await self.db.flush()
        return pos

    async def update_position_price(self, position_id: uuid.UUID, current_price: float) -> Position | None:
        result = await self.db.execute(select(Position).where(Position.id == position_id))
        pos = result.scalar_one_or_none()
        if not pos or pos.status == "CLOSED":
            return None

        price_move = current_price - float(pos.entry_price)
        if pos.direction == "NO":
            price_move = -price_move

        pos.current_price = current_price
        pos.unrealized_pnl = price_move * float(pos.size)
        await self.db.flush()
        return pos

    async def get_open_positions(self, strategy_name: str | None = None) -> list[Position]:
        query = select(Position).where(Position.status == "OPEN")
        if strategy_name:
            query = query.where(Position.strategy_name == strategy_name)
        query = query.order_by(desc(Position.opened_at))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_position_history(self, limit: int = 50) -> list[Position]:
        result = await self.db.execute(
            select(Position).order_by(desc(Position.opened_at)).limit(limit)
        )
        return list(result.scalars().all())

    async def get_portfolio_history(self, hours: int = 168) -> list[PortfolioSnapshot]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await self.db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.timestamp >= cutoff)
            .order_by(PortfolioSnapshot.timestamp)
        )
        return list(result.scalars().all())

    async def _resolve_category(self, position: Position) -> str:
        if position.market_id:
            result = await self.db.execute(
                select(Market.category).where(Market.id == position.market_id)
            )
            cat = result.scalar_one_or_none()
            if cat:
                return cat
        if position.market_condition_id and "-" in position.market_condition_id:
            return position.market_condition_id.split("-")[0]
        return "other"

    async def compute_portfolio_snapshot(self) -> PortfolioSnapshot:
        open_positions = await self.get_open_positions()
        closed_positions = await self.db.execute(
            select(Position).where(Position.status == "CLOSED")
        )
        closed = list(closed_positions.scalars().all())

        total_exposure = sum(float(p.size * (p.current_price or p.entry_price)) for p in open_positions)
        total_unrealized = sum(float(p.unrealized_pnl or 0.0) for p in open_positions)
        total_realized = sum(float(p.realized_pnl or 0.0) for p in closed)
        portfolio_value = total_exposure + total_unrealized + total_realized

        peak = portfolio_value
        last_snapshot = await self.db.execute(
            select(PortfolioSnapshot).order_by(desc(PortfolioSnapshot.timestamp)).limit(1)
        )
        last = last_snapshot.scalar_one_or_none()
        if last and last.peak_value:
            peak = max(float(last.peak_value), portfolio_value)

        drawdown = (peak - portfolio_value) / peak if peak > 0 else 0

        category_exposure = {}
        for pos in open_positions:
            cat = await self._resolve_category(pos)
            category_exposure[cat] = category_exposure.get(cat, 0) + float(pos.size * (pos.current_price or pos.entry_price))

        snapshot = PortfolioSnapshot(
            total_exposure=total_exposure,
            cash_reserve=0.0,
            open_positions=len(open_positions),
            total_unrealized_pnl=total_unrealized,
            total_realized_pnl=total_realized,
            portfolio_value=portfolio_value,
            peak_value=peak,
            drawdown=drawdown,
            category_exposure=category_exposure,
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def get_portfolio_summary(self) -> dict:
        open_positions = await self.get_open_positions()
        closed_result = await self.db.execute(
            select(Position).where(Position.status == "CLOSED")
        )
        closed = list(closed_result.scalars().all())

        total_exposure = sum(float(p.size) for p in open_positions)
        total_unrealized_pnl = sum(float(p.unrealized_pnl or 0.0) for p in open_positions)
        total_realized_pnl = sum(float(p.realized_pnl or 0.0) for p in closed)

        recent_snapshots = await self.db.execute(
            select(PortfolioSnapshot).order_by(desc(PortfolioSnapshot.timestamp)).limit(30)
        )
        snapshots = list(recent_snapshots.scalars().all())
        latest = snapshots[0] if snapshots else None

        pnl_history = [float(s.total_realized_pnl or 0) + float(s.total_unrealized_pnl or 0) for s in snapshots]
        portfolio_values = [float(s.portfolio_value or 0) for s in snapshots]

        return {
            "open_positions": len(open_positions),
            "total_exposure": total_exposure,
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_realized_pnl": total_realized_pnl,
            "total_pnl": total_unrealized_pnl + total_realized_pnl,
            "current_value": total_exposure + total_unrealized_pnl + total_realized_pnl,
            "drawdown": float(latest.drawdown) if latest and latest.drawdown else 0,
            "peak_value": float(latest.peak_value) if latest and latest.peak_value else 0,
            "pnl_history": pnl_history,
            "portfolio_value_history": portfolio_values,
            "positions": [
                {
                    "id": str(p.id),
                    "market_condition_id": p.market_condition_id,
                    "direction": p.direction,
                    "size": float(p.size),
                    "entry_price": float(p.entry_price),
                    "current_price": float(p.current_price) if p.current_price else None,
                    "unrealized_pnl": float(p.unrealized_pnl) if p.unrealized_pnl else 0,
                    "strategy": p.strategy_name,
                    "opened_at": p.opened_at.isoformat() if p.opened_at else None,
                    "status": p.status,
                }
                for p in open_positions + closed[-20:]
            ],
        }

    async def compute_correlations(self, window_hours: int = 24) -> list[MarketCorrelation]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        markets_result = await self.db.execute(
            select(Market).where(Market.resolved == False)
        )
        markets = list(markets_result.scalars().all())

        correlations = []
        for i in range(len(markets)):
            for j in range(i + 1, len(markets)):
                m_a = markets[i]
                m_b = markets[j]

                prices_a = await self.db.execute(
                    select(SignalOutcome.entry_probability, SignalOutcome.entry_timestamp)
                    .where(
                        SignalOutcome.market_id == m_a.id,
                        SignalOutcome.entry_timestamp >= cutoff,
                    )
                    .order_by(SignalOutcome.entry_timestamp)
                )
                prices_b = await self.db.execute(
                    select(SignalOutcome.entry_probability, SignalOutcome.entry_timestamp)
                    .where(
                        SignalOutcome.market_id == m_b.id,
                        SignalOutcome.entry_timestamp >= cutoff,
                    )
                    .order_by(SignalOutcome.entry_timestamp)
                )
                pa = list(prices_a.all())
                pb = list(prices_b.all())

                if len(pa) < 5 or len(pb) < 5:
                    continue

                prices_a_dict = {r.timestamp.timestamp(): float(r.entry_probability) for r in pa}
                prices_b_dict = {r.timestamp.timestamp(): float(r.entry_probability) for r in pb}
                common_times = sorted(set(prices_a_dict.keys()) & set(prices_b_dict.keys()))

                if len(common_times) < 5:
                    continue

                va = [prices_a_dict[t] for t in common_times]
                vb = [prices_b_dict[t] for t in common_times]
                n = len(va)

                mean_a = sum(va) / n
                mean_b = sum(vb) / n
                cov = sum((va[i] - mean_a) * (vb[i] - mean_b) for i in range(n)) / n
                std_a = math.sqrt(sum((v - mean_a) ** 2 for v in va) / n)
                std_b = math.sqrt(sum((v - mean_b) ** 2 for v in vb) / n)
                corr = cov / (std_a * std_b) if std_a * std_b > 0 else 0

                mc = MarketCorrelation(
                    market_a_id=m_a.id,
                    market_b_id=m_b.id,
                    correlation_coefficient=corr,
                    sample_size=n,
                    window_hours=window_hours,
                )
                self.db.add(mc)
                correlations.append(mc)

        await self.db.flush()
        return correlations

    async def get_correlations(self, threshold: float = 0.5) -> list[dict]:
        result = await self.db.execute(
            select(MarketCorrelation)
            .where(MarketCorrelation.correlation_coefficient >= threshold)
            .order_by(desc(MarketCorrelation.correlation_coefficient))
            .limit(50)
        )
        rows = list(result.scalars().all())
        output = []
        for r in rows:
            m_a = await self.db.get(Market, r.market_a_id)
            m_b = await self.db.get(Market, r.market_b_id)
            output.append({
                "market_a": m_a.slug if m_a else str(r.market_a_id),
                "market_b": m_b.slug if m_b else str(r.market_b_id),
                "correlation": float(r.correlation_coefficient),
                "sample_size": r.sample_size,
                "window_hours": r.window_hours,
            })
        return output
