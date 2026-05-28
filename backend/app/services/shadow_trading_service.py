import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade, Market, MarketEvent
from app.core.logging import logger


@dataclass
class ShadowPosition:
    id: str
    market_id: str
    strategy: str
    side: str
    outcome: str
    size: float
    entry_price: float
    entry_timestamp: datetime
    exit_price: float | None = None
    exit_timestamp: datetime | None = None
    pnl: float | None = None
    slippage: float | None = None
    latency_ms: float | None = None
    missed_fill: bool = False
    stale_fill: bool = False


@dataclass
class ShadowMetrics:
    live_expectancy: float
    live_sharpe: float
    live_drawdown: float
    latency_adjusted_pnl: float
    total_trades: int = 0
    missed_fills: int = 0
    stale_fills: int = 0
    avg_latency_ms: float = 0.0
    avg_slippage: float = 0.0
    equity_curve: list[float] = field(default_factory=list)


class ShadowTradingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._positions: dict[str, ShadowPosition] = {}
        self._equity_curve: list[float] = []
        self._initial_capital = 10000.0

    async def open_shadow_position(
        self,
        market_id: str,
        strategy: str,
        side: str,
        outcome: str,
        size: float,
        entry_price: float,
    ) -> ShadowPosition:
        pos_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        position = ShadowPosition(
            id=pos_id,
            market_id=market_id,
            strategy=strategy,
            side=side,
            outcome=outcome,
            size=size,
            entry_price=entry_price,
            entry_timestamp=now,
        )
        self._positions[pos_id] = position
        return position

    async def update_shadow_position(
        self,
        position_id: str,
        exit_price: float | None = None,
        slippage: float | None = None,
        latency_ms: float | None = None,
        missed_fill: bool = False,
        stale_fill: bool = False,
    ) -> ShadowPosition | None:
        pos = self._positions.get(position_id)
        if not pos:
            return None

        if exit_price is not None:
            pos.exit_price = exit_price
            pos.exit_timestamp = datetime.now(timezone.utc)
            if pos.side == "buy":
                pos.pnl = (exit_price - pos.entry_price) * pos.size
            else:
                pos.pnl = (pos.entry_price - exit_price) * pos.size

        pos.slippage = slippage
        pos.latency_ms = latency_ms
        pos.missed_fill = missed_fill
        pos.stale_fill = stale_fill

        self._update_equity()
        return pos

    def _update_equity(self):
        total_pnl = sum(p.pnl or 0 for p in self._positions.values())
        equity = self._initial_capital + total_pnl
        self._equity_curve.append(equity)
        if len(self._equity_curve) > 1000:
            self._equity_curve = self._equity_curve[-1000:]

    def get_shadow_metrics(self) -> ShadowMetrics:
        closed = [p for p in self._positions.values() if p.pnl is not None]
        if not closed:
            return ShadowMetrics(
                live_expectancy=0.0, live_sharpe=0.0,
                live_drawdown=0.0, latency_adjusted_pnl=0.0,
            )

        pnls = [p.pnl for p in closed if p.pnl is not None]
        missed = sum(1 for p in closed if p.missed_fill)
        stale = sum(1 for p in closed if p.stale_fill)
        latencies = [p.latency_ms for p in closed if p.latency_ms is not None]
        slippages = [p.slippage for p in closed if p.slippage is not None]

        expectancy = sum(pnls) / len(pnls) if pnls else 0.0

        mean = sum(pnls) / len(pnls) if pnls else 0
        variance = sum((p - mean) ** 2 for p in pnls) / len(pnls) if len(pnls) > 1 else 1
        sharpe = mean / (variance ** 0.5 + 0.0001) * (252 ** 0.5)

        peak = max(self._equity_curve) if self._equity_curve else self._initial_capital
        trough = min(self._equity_curve) if self._equity_curve else self._initial_capital
        drawdown = (peak - trough) / peak if peak > 0 else 0

        latency_penalty = (sum(latencies) / len(latencies) * 0.001) if latencies else 0
        latency_adjusted_pnl = sum(pnls) - latency_penalty

        return ShadowMetrics(
            live_expectancy=round(expectancy, 6),
            live_sharpe=round(sharpe, 4),
            live_drawdown=round(drawdown, 4),
            latency_adjusted_pnl=round(latency_adjusted_pnl, 4),
            total_trades=len(closed),
            missed_fills=missed,
            stale_fills=stale,
            avg_latency_ms=round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            avg_slippage=round(sum(slippages) / len(slippages), 6) if slippages else 0.0,
            equity_curve=self._equity_curve[-100:] if self._equity_curve else [],
        )

    def get_positions(self) -> list[ShadowPosition]:
        return list(self._positions.values())

    def get_open_positions(self) -> list[ShadowPosition]:
        return [p for p in self._positions.values() if p.pnl is None]

    def reset(self):
        self._positions = {}
        self._equity_curve = []

    async def sync_from_live_trades(self, strategy_name: str | None = None):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        query = select(Trade).where(
            Trade.created_at >= cutoff,
            Trade.status.in_(["open", "closed"]),
        )
        if strategy_name:
            query = query.where(Trade.agent_id == strategy_name)
        query = query.order_by(Trade.created_at.asc())
        result = await self.db.execute(query)
        trades = list(result.scalars().all())

        for t in trades:
            if str(t.id) in self._positions:
                continue
            market_yes_price = float(t.filled_price or t.price or 0.5)
            outcome_price = 1.0 - market_yes_price if t.outcome == "NO" else market_yes_price
            pos = ShadowPosition(
                id=str(t.id),
                market_id=str(t.market_id) if t.market_id else "",
                strategy=t.agent_id or "unknown",
                side=t.side,
                outcome=t.outcome,
                size=float(t.filled_size or t.size or 0),
                entry_price=outcome_price,
                entry_timestamp=t.created_at,
            )
            if t.status == "closed":
                pos.exit_price = outcome_price
                pos.exit_timestamp = t.exit_timestamp or t.updated_at
                if t.side == "buy":
                    pos.pnl = (outcome_price - outcome_price) * pos.size
                else:
                    pos.pnl = (outcome_price - outcome_price) * pos.size
                pos.pnl = float(t.pnl or 0)
                pos.slippage = float(t.slippage or 0)
            self._positions[str(t.id)] = pos

        self._update_equity()
