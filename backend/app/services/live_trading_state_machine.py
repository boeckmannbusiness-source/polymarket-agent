from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Trade, MarketEvent
from app.core.logging import logger


class TradingState(Enum):
    SHADOW = "SHADOW"
    MICRO_LIVE = "MICRO_LIVE"
    REDUCED_RISK = "REDUCED_RISK"
    KILL_SWITCH = "KILL_SWITCH"
    DISABLED = "DISABLED"


@dataclass
class StateTransition:
    from_state: TradingState
    to_state: TradingState
    reason: str
    timestamp: datetime


class LiveTradingStateMachine:
    MAX_CONSECUTIVE_LOSSES = 3
    MAX_DAILY_DRAWDOWN_PCT = 0.02
    MAX_CONCURRENT_POSITIONS = 5
    MAX_PER_TRADE_PCT = 0.005

    def __init__(self, db: AsyncSession):
        self.db = db
        self._state = TradingState.SHADOW
        self._transitions: list[StateTransition] = []
        self._transition_history: list[dict] = []

    @property
    def state(self) -> TradingState:
        return self._state

    async def evaluate(self, risk_overlay_status: str | None = None) -> TradingState:
        previous = self._state
        new_state = self._state

        if risk_overlay_status == "STOPPED":
            new_state = TradingState.KILL_SWITCH

        elif self._state == TradingState.SHADOW:
            shadow_ok = await self._check_shadow_readiness()
            if shadow_ok:
                new_state = TradingState.MICRO_LIVE

        elif self._state == TradingState.MICRO_LIVE:
            if await self._check_consecutive_losses():
                new_state = TradingState.REDUCED_RISK
            if await self._check_drawdown():
                new_state = TradingState.KILL_SWITCH

        elif self._state == TradingState.REDUCED_RISK:
            if await self._check_consecutive_losses():
                new_state = TradingState.KILL_SWITCH
            if risk_overlay_status == "STOPPED":
                new_state = TradingState.KILL_SWITCH

        elif self._state in (TradingState.KILL_SWITCH, TradingState.DISABLED):
            pass

        if new_state != previous:
            self._transitions.append(StateTransition(
                from_state=previous,
                to_state=new_state,
                reason=f"risk_overlay={risk_overlay_status}",
                timestamp=datetime.now(timezone.utc),
            ))
            self._transition_history.append({
                "from": previous.value,
                "to": new_state.value,
                "reason": f"risk_overlay={risk_overlay_status}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            logger.warning("state_transition", from_state=previous.value, to_state=new_state.value)
            self._state = new_state

        return self._state

    async def _check_shadow_readiness(self) -> bool:
        result = await self.db.execute(
            select(func.count(Trade.id))
            .where(Trade.status == "closed")
        )
        count = result.scalar() or 0
        return count >= 20

    async def _check_consecutive_losses(self) -> bool:
        result = await self.db.execute(
            select(Trade)
            .where(Trade.status == "closed", Trade.pnl.isnot(None))
            .order_by(desc(Trade.exit_timestamp))
            .limit(self.MAX_CONSECUTIVE_LOSSES)
        )
        trades = list(result.scalars().all())
        if len(trades) < self.MAX_CONSECUTIVE_LOSSES:
            return False
        return all(float(t.pnl or 0) < 0 for t in trades[:self.MAX_CONSECUTIVE_LOSSES])

    async def _check_drawdown(self) -> bool:
        result = await self.db.execute(
            select(func.sum(Trade.pnl))
            .where(Trade.exit_timestamp >= datetime.now(timezone.utc) - timedelta(days=1))
        )
        daily_pnl = float(result.scalar() or 0)
        capital = settings.PAPER_INITIAL_CAPITAL
        return daily_pnl < -capital * self.MAX_DAILY_DRAWDOWN_PCT

    @property
    def hard_caps(self) -> dict[str, Any]:
        base = {"max_concurrent_positions": self.MAX_CONCURRENT_POSITIONS}
        if self._state == TradingState.SHADOW:
            base.update({"max_per_trade_pct": 0.0, "max_daily_drawdown_pct": self.MAX_DAILY_DRAWDOWN_PCT})
        elif self._state == TradingState.MICRO_LIVE:
            base.update({"max_per_trade_pct": self.MAX_PER_TRADE_PCT, "max_daily_drawdown_pct": self.MAX_DAILY_DRAWDOWN_PCT})
        elif self._state == TradingState.REDUCED_RISK:
            base.update({"max_per_trade_pct": self.MAX_PER_TRADE_PCT * 0.5, "max_daily_drawdown_pct": self.MAX_DAILY_DRAWDOWN_PCT * 0.5, "max_concurrent_positions": 3})
        elif self._state == TradingState.KILL_SWITCH:
            base.update({"max_per_trade_pct": 0.0, "max_concurrent_positions": 0})
        elif self._state == TradingState.DISABLED:
            base.update({"max_per_trade_pct": 0.0, "max_concurrent_positions": 0})
        return base

    def get_transition_history(self) -> list[dict]:
        return list(self._transition_history)

    def force_state(self, state: TradingState, reason: str = "manual"):
        self._transitions.append(StateTransition(
            from_state=self._state,
            to_state=state,
            reason=reason,
            timestamp=datetime.now(timezone.utc),
        ))
        self._transition_history.append({
            "from": self._state.value,
            "to": state.value,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._state = state
