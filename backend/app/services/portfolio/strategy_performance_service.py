from datetime import datetime, timezone, timedelta
from collections import defaultdict

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Fill, Trade, ExchangeOrder
from app.schemas.portfolio import StrategyPerformance, PnlPoint


class StrategyPerformanceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_strategy_pnl_curve(self, agent_id: str) -> list[PnlPoint]:
        result = await self.db.execute(
            select(Fill)
            .join(Trade, Fill.trade_id == Trade.id)
            .where(Trade.agent_id == agent_id)
            .order_by(Fill.filled_at)
        )
        fills = list(result.scalars().all())

        cumulative = 0.0
        peak = 0.0
        points = []

        bucket: dict[str, list] = defaultdict(list)
        for f in fills:
            ts = f.filled_at.replace(second=0, microsecond=0)
            key = ts.isoformat()
            trade_pnl = float(f.size) * float(f.price) * (1 if f.side == "sell" else -1)
            bucket[key].append(trade_pnl)

        for ts_key in sorted(bucket.keys()):
            period_pnl = sum(bucket[ts_key])
            cumulative += period_pnl
            peak = max(peak, cumulative)
            drawdown = (peak - cumulative) / peak if peak > 0 else 0.0
            points.append(PnlPoint(
                timestamp=datetime.fromisoformat(ts_key),
                cumulative_pnl=round(cumulative, 4),
                drawdown=round(drawdown, 6),
            ))

        return points

    async def get_strategy_summary(self, agent_id: str) -> StrategyPerformance:
        result = await self.db.execute(
            select(Trade).where(Trade.agent_id == agent_id)
        )
        trades = list(result.scalars().all())

        result = await self.db.execute(
            select(Fill)
            .join(Trade, Fill.trade_id == Trade.id)
            .where(Trade.agent_id == agent_id)
        )
        fills = list(result.scalars().all())

        total_trades = len(trades)
        wins = 0
        losses = 0
        total_duration = timedelta(0)
        duration_count = 0
        total_volume = sum(float(f.size) for f in fills)
        total_fees = sum(float(f.fee) for f in fills)

        realized_pnl = 0.0
        buy_fills: dict = defaultdict(lambda: {"size": 0.0, "cost": 0.0})
        sell_fills: dict = defaultdict(lambda: {"size": 0.0, "revenue": 0.0})

        for f in fills:
            key = f"{f.market_id}:{f.outcome}"
            val = float(f.size) * float(f.price)
            if f.side == "buy":
                buy_fills[key]["size"] += float(f.size)
                buy_fills[key]["cost"] += val + float(f.fee)
            else:
                sell_fills[key]["size"] += float(f.size)
                sell_fills[key]["revenue"] += val - float(f.fee)

        for key in set(list(buy_fills.keys()) + list(sell_fills.keys())):
            b = buy_fills[key]
            s = sell_fills[key]
            total_sell_revenue = s["revenue"]
            total_sell_size = s["size"]
            total_buy_cost = b["cost"]
            total_buy_size = b["size"]
            allocated_cost = (total_buy_cost * (total_sell_size / total_buy_size)) if total_buy_size > 0 else 0
            pnl = total_sell_revenue - allocated_cost
            realized_pnl += pnl

        for t in trades:
            if t.pnl is not None:
                if float(t.pnl) > 0:
                    wins += 1
                elif float(t.pnl) < 0:
                    losses += 1
            if t.entry_timestamp and t.exit_timestamp:
                total_duration += t.exit_timestamp - t.entry_timestamp
                duration_count += 1

        for t in trades:
            if t.entry_timestamp and t.exit_timestamp:
                total_duration += t.exit_timestamp - t.entry_timestamp
                duration_count += 1

        avg_duration = (total_duration / duration_count).total_seconds() / 3600 if duration_count > 0 else 0.0
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

        pnl_curve = await self.get_strategy_pnl_curve(agent_id)
        cumulative_pnl = pnl_curve[-1].cumulative_pnl if pnl_curve else 0.0
        max_dd = max((p.drawdown for p in pnl_curve), default=0.0)

        returns = [pnl_curve[i].cumulative_pnl - pnl_curve[i - 1].cumulative_pnl for i in range(1, len(pnl_curve))]
        avg_return = sum(returns) / len(returns) if returns else 0.0
        std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5 if returns else 1.0
        sharpe = (avg_return / std_return * (365 * 24) ** 0.5) if std_return > 0 else None

        return StrategyPerformance(
            agent_id=agent_id,
            total_trades=total_trades,
            wins=wins,
            losses=losses,
            win_rate=round(win_rate, 2),
            cumulative_pnl=round(cumulative_pnl, 4),
            realized_pnl=round(realized_pnl, 4),
            unrealized_pnl=round(cumulative_pnl - realized_pnl, 4),
            avg_trade_duration_hours=round(avg_duration, 2),
            max_drawdown=round(max_dd, 6),
            sharpe_ratio=round(sharpe, 4) if sharpe is not None else None,
            total_volume=round(total_volume, 4),
            total_fees=round(total_fees, 4),
            pnl_curve=pnl_curve,
            created_at=datetime.now(timezone.utc),
        )
