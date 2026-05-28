import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade, MarketEvent
from app.models.portfolio import PortfolioSnapshot
from app.models.safety import SafetyState
from app.models.strategy import StrategyConfigRecord
from app.core.logging import logger


@dataclass
class SystemHealthSnapshot:
    timestamp: datetime
    total_trades: int
    open_trades: int
    portfolio_value: float
    drawdown: float
    kill_switch_active: bool
    circuit_breaker_active: bool
    active_strategies: int
    disabled_strategies: int
    ws_events_last_minute: int
    db_event_count: int
    error_count: int


class SystemHealthStore:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._health_history: list[SystemHealthSnapshot] = []
        self._max_history = 168

    async def record_snapshot(self) -> SystemHealthSnapshot:
        now = datetime.now(timezone.utc)

        total_trades = await self.db.execute(select(func.count(Trade.id)))
        total_trades = total_trades.scalar() or 0

        open_trades = await self.db.execute(
            select(func.count(Trade.id)).where(Trade.status.in_(["open", "pending"]))
        )
        open_trades = open_trades.scalar() or 0

        snapshot = await self.db.execute(
            select(PortfolioSnapshot).order_by(desc(PortfolioSnapshot.timestamp)).limit(1)
        )
        ps = snapshot.scalar_one_or_none()
        portfolio_value = float(ps.portfolio_value or 0) if ps else 0
        drawdown = float(ps.drawdown or 0) if ps else 0

        safety = await self.db.execute(
            select(SafetyState).order_by(desc(SafetyState.updated_at)).limit(1)
        )
        ss = safety.scalar_one_or_none()
        kill_switch = ss.kill_switch_active if ss else False
        circuit_breaker = ss.circuit_breaker_active if ss else False

        strategies = await self.db.execute(select(StrategyConfigRecord))
        all_strats = list(strategies.scalars().all())
        active = sum(1 for s in all_strats if s.enabled)
        disabled = sum(1 for s in all_strats if not s.enabled)

        ws_cutoff = now - timedelta(minutes=1)
        ws_events = await self.db.execute(
            select(func.count(MarketEvent.id))
            .where(MarketEvent.timestamp >= ws_cutoff)
        )
        ws_events = ws_events.scalar() or 0

        db_events = await self.db.execute(select(func.count(MarketEvent.id)))
        db_events = db_events.scalar() or 0

        health = SystemHealthSnapshot(
            timestamp=now,
            total_trades=total_trades,
            open_trades=open_trades,
            portfolio_value=portfolio_value,
            drawdown=drawdown,
            kill_switch_active=kill_switch,
            circuit_breaker_active=circuit_breaker,
            active_strategies=active,
            disabled_strategies=disabled,
            ws_events_last_minute=ws_events,
            db_event_count=db_events,
            error_count=0,
        )

        self._health_history.append(health)
        if len(self._health_history) > self._max_history:
            self._health_history = self._health_history[-self._max_history:]

        return health

    async def check_alerts(self) -> list[str]:
        alerts = []
        now = datetime.now(timezone.utc)

        recent = self._health_history[-10:] if len(self._health_history) >= 10 else self._health_history
        if len(recent) >= 2:
            reconnect_count = sum(
                1 for i in range(1, len(recent))
                if recent[i].ws_events_last_minute == 0 and recent[i - 1].ws_events_last_minute > 0
            )
            if reconnect_count >= 3:
                alerts.append(f"ws_reconnect_storm_{reconnect_count}_disconnections_detected")

            drawdown = recent[-1].drawdown
            if drawdown > 0.15:
                alerts.append(f"drawdown_spike_{drawdown:.2%}_exceeds_15%")

        recent_trades = await self.db.execute(
            select(Trade)
            .where(Trade.status == "closed", Trade.exit_timestamp >= now - timedelta(hours=1))
        )
        recent_trades_list = list(recent_trades.scalars().all())
        if recent_trades_list:
            slippages = [float(t.slippage or 0) for t in recent_trades_list]
            avg_slip = sum(slippages) / len(slippages)
            if avg_slip > 0.01:
                alerts.append(f"slippage_anomaly_avg_{avg_slip:.4f}_in_last_hour")

        if len(self._health_history) >= 2:
            last = self._health_history[-1]
            prev = self._health_history[-2]
            if last.ws_events_last_minute == 0 and prev.ws_events_last_minute == 0:
                alerts.append("no_event_period_2min_consecutive")

        if recent:
            disabled = await self.db.execute(
                select(func.count(StrategyConfigRecord.id))
                .where(StrategyConfigRecord.enabled == False)
                .where(StrategyConfigRecord.updated_at >= now - timedelta(hours=1))
            )
            if (disabled.scalar() or 0) > 0:
                alerts.append("strategy_disable_event_in_last_hour")

        return alerts

    def get_history(self, limit: int = 50) -> list[SystemHealthSnapshot]:
        return self._health_history[-limit:]

    def get_latest(self) -> SystemHealthSnapshot | None:
        return self._health_history[-1] if self._health_history else None
