import uuid
from enum import Enum
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field

from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Position, SafetyState, MarketEvent, Market


class CircuitBreakerReason(Enum):
    MAX_LOSS = "max_loss_exceeded"
    MAX_POSITIONS = "max_positions_exceeded"
    MAX_EXPOSURE = "max_exposure_exceeded"
    STALE_DATA = "stale_data_detected"
    STRATEGY_QUARANTINE = "strategy_quarantined"
    MANUAL_KILL = "manual_kill_switch"
    CONSECUTIVE_LOSSES = "consecutive_losses_exceeded"


@dataclass
class SafetyCheckResult:
    approved: bool
    reasons: list[str] = field(default_factory=list)
    circuit_breaker: CircuitBreakerReason | None = None


class SafetyService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.max_daily_loss = -500.0
        self.max_open_positions = 20
        self.max_total_exposure = 50000.0
        self.max_consecutive_losses = 5
        self.stale_data_minutes = 30
        self.quarantine_threshold_win_rate = 0.3
        self.quarantine_min_signals = 10

    async def get_state(self) -> dict:
        result = await self.db.execute(
            select(SafetyState).order_by(desc(SafetyState.updated_at)).limit(1)
        )
        state = result.scalar_one_or_none()
        if not state:
            return {
                "kill_switch_active": False,
                "circuit_breaker_active": False,
                "circuit_breaker_reason": None,
                "quarantined_strategies": [],
                "daily_pnl": 0.0,
                "checks_passed": 0,
                "checks_failed": 0,
            }
        return {
            "kill_switch_active": state.kill_switch_active,
            "circuit_breaker_active": state.circuit_breaker_active,
            "circuit_breaker_reason": state.circuit_breaker_reason,
            "quarantined_strategies": state.quarantined_strategies or [],
            "daily_pnl": float(state.daily_pnl) if state.daily_pnl else 0.0,
            "checks_passed": state.checks_passed,
            "checks_failed": state.checks_failed,
        }

    async def check_trade_approval(self, strategy_name: str, size: float, confidence: float) -> SafetyCheckResult:
        state = await self.get_state()

        if state["kill_switch_active"]:
            return SafetyCheckResult(approved=False, reasons=["Kill switch is active"], circuit_breaker=CircuitBreakerReason.MANUAL_KILL)

        if state["circuit_breaker_active"]:
            return SafetyCheckResult(approved=False, reasons=[f"Circuit breaker active: {state['circuit_breaker_reason']}"],
                                     circuit_breaker=CircuitBreakerReason(state["circuit_breaker_reason"]))

        if strategy_name in state["quarantined_strategies"]:
            return SafetyCheckResult(approved=False, reasons=[f"Strategy {strategy_name} is quarantined"],
                                     circuit_breaker=CircuitBreakerReason.STRATEGY_QUARANTINE)

        result = await self.db.execute(
            select(Position).where(Position.status == "OPEN")
        )
        open_positions = list(result.scalars().all())
        if len(open_positions) >= self.max_open_positions:
            return SafetyCheckResult(approved=False, reasons=["Max open positions reached"],
                                     circuit_breaker=CircuitBreakerReason.MAX_POSITIONS)

        total_exposure = sum(float(p.size) for p in open_positions)
        if total_exposure + size > self.max_total_exposure:
            return SafetyCheckResult(approved=False, reasons=["Max total exposure exceeded"],
                                     circuit_breaker=CircuitBreakerReason.MAX_EXPOSURE)

        recent_trades = await self.db.execute(
            select(Position)
            .where(Position.strategy_name == strategy_name, Position.status == "CLOSED")
            .order_by(desc(Position.closed_at))
            .limit(self.max_consecutive_losses)
        )
        recent = list(recent_trades.scalars().all())
        if len(recent) >= self.max_consecutive_losses:
            consecutive_losses = all(
                (p.realized_pnl or 0) <= 0 for p in recent[:self.max_consecutive_losses]
            )
            if consecutive_losses:
                return SafetyCheckResult(approved=False, reasons=["Consecutive losses exceeded"],
                                         circuit_breaker=CircuitBreakerReason.CONSECUTIVE_LOSSES)

        stale = await self._check_stale_data()
        if stale:
            return SafetyCheckResult(approved=False, reasons=["Stale market data detected"],
                                     circuit_breaker=CircuitBreakerReason.STALE_DATA)

        await self._update_safety_state(approved=True)
        return SafetyCheckResult(approved=True, reasons=[])

    async def _check_stale_data(self) -> bool:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=self.stale_data_minutes)
        result = await self.db.execute(
            select(MarketEvent).order_by(desc(MarketEvent.timestamp)).limit(1)
        )
        latest = result.scalar_one_or_none()
        if latest is None:
            return True
        ts = latest.timestamp.replace(tzinfo=timezone.utc) if latest.timestamp.tzinfo is None else latest.timestamp
        return ts < cutoff

    async def _update_safety_state(self, approved: bool):
        result = await self.db.execute(
            select(SafetyState).order_by(desc(SafetyState.updated_at)).limit(1)
        )
        state = result.scalar_one_or_none()
        if not state:
            state = SafetyState(id=uuid.uuid4(), daily_pnl=0.0)
            self.db.add(state)

        if approved:
            state.checks_passed = (state.checks_passed or 0) + 1
        else:
            state.checks_failed = (state.checks_failed or 0) + 1
        state.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def set_kill_switch(self, active: bool, reason: str | None = None):
        result = await self.db.execute(
            select(SafetyState).order_by(desc(SafetyState.updated_at)).limit(1)
        )
        state = result.scalar_one_or_none()
        if not state:
            state = SafetyState(id=uuid.uuid4(), daily_pnl=0.0)
            self.db.add(state)
        state.kill_switch_active = active
        if active:
            state.circuit_breaker_active = True
            state.circuit_breaker_reason = reason or CircuitBreakerReason.MANUAL_KILL.value
        else:
            state.circuit_breaker_active = False
            state.circuit_breaker_reason = None
        state.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def quarantine_strategy(self, strategy_name: str, quarantine: bool = True):
        result = await self.db.execute(
            select(SafetyState).order_by(desc(SafetyState.updated_at)).limit(1)
        )
        state = result.scalar_one_or_none()
        if not state:
            state = SafetyState(id=uuid.uuid4(), daily_pnl=0.0, quarantined_strategies=[])
            self.db.add(state)

        current = list(state.quarantined_strategies or [])
        if quarantine and strategy_name not in current:
            current.append(strategy_name)
        elif not quarantine and strategy_name in current:
            current.remove(strategy_name)
        state.quarantined_strategies = current
        state.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def update_daily_pnl(self, pnl_change: float):
        result = await self.db.execute(
            select(SafetyState).order_by(desc(SafetyState.updated_at)).limit(1)
        )
        state = result.scalar_one_or_none()
        if not state:
            state = SafetyState(id=uuid.uuid4(), daily_pnl=0.0)
            self.db.add(state)

        state.daily_pnl = (state.daily_pnl or 0.0) + pnl_change
        if state.daily_pnl <= self.max_daily_loss:
            state.circuit_breaker_active = True
            state.circuit_breaker_reason = CircuitBreakerReason.MAX_LOSS.value
        state.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
