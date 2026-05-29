import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Trade, MarketEvent
from app.models.portfolio import PortfolioSnapshot
from app.core.logging import logger


@dataclass
class RiskState:
    status: str  # "ACTIVE" | "REDUCED" | "STOPPED" | "MARKET_DATA_UNSTABLE"
    reason: str
    cooldown_until: datetime | None = None


class RiskOverlay:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._state = RiskState(status="ACTIVE", reason="initialized")
        self._portfolio_drawdown_curve: list[float] = []
        self._consecutive_losses = 0
        self._baseline_slippage: float | None = None
        self._last_ws_timestamp: datetime | None = None
        self._cooldown_end: datetime | None = None
        self._reconnect_count_last_10min = 0
        self._last_reconnect_reset: datetime = datetime.now(timezone.utc)

    async def check(self) -> RiskState:
        previous_state = self._state.status

        dd_check = await self._check_drawdown()
        if dd_check.status == "STOPPED":
            self._state = dd_check
            return self._state

        loss_check = await self._check_consecutive_losses()
        if loss_check.status == "STOPPED":
            self._state = loss_check
            return self._state

        slip_check = await self._check_slippage_spike()
        if slip_check.status == "STOPPED":
            self._state = slip_check
            return self._state

        liq_check = await self._check_liquidity_collapse()
        if liq_check.status != "ACTIVE":
            self._state = liq_check
            return self._state

        ws_check = await self._check_ws_stall()
        if ws_check.status != "ACTIVE":
            self._state = ws_check
            return self._state

        md_check = await self._check_market_data_stability()
        if md_check.status == "MARKET_DATA_UNSTABLE":
            self._state = md_check
            return self._state

        if previous_state != "ACTIVE":
            if self._cooldown_end and datetime.now(timezone.utc) >= self._cooldown_end:
                self._state = RiskState(status="ACTIVE", reason="cooldown_expired")
                return self._state

        if self._cooldown_end:
            self._state = RiskState(
                status="REDUCED" if self._cooldown_end > datetime.now(timezone.utc) else "ACTIVE",
                reason=f"cooling_down_until_{self._cooldown_end.isoformat()}",
                cooldown_until=self._cooldown_end,
            )
        else:
            self._state = RiskState(status="ACTIVE", reason="all_checks_passed")

        return self._state

    async def _check_drawdown(self) -> RiskState:
        result = await self.db.execute(
            select(PortfolioSnapshot)
            .order_by(PortfolioSnapshot.timestamp.desc())
            .limit(30)
        )
        snapshots = list(result.scalars().all())
        if not snapshots:
            return RiskState(status="ACTIVE", reason="no_snapshot_data")

        latest = snapshots[0]
        peak = float(latest.peak_value or 0)
        current = float(latest.portfolio_value or 0)
        drawdown = (peak - current) / peak if peak > 0 else 0

        self._portfolio_drawdown_curve.append(drawdown)
        if len(self._portfolio_drawdown_curve) > 100:
            self._portfolio_drawdown_curve = self._portfolio_drawdown_curve[-100:]

        if drawdown > 0.20:
            self._cooldown_end = datetime.now(timezone.utc) + timedelta(hours=1)
            return RiskState(
                status="STOPPED",
                reason=f"portfolio_drawdown_{drawdown:.2%}_exceeds_20%",
                cooldown_until=self._cooldown_end,
            )
        elif drawdown > 0.12:
            return RiskState(
                status="REDUCED",
                reason=f"portfolio_drawdown_{drawdown:.2%}_above_12%_threshold",
            )

        return RiskState(status="ACTIVE", reason="drawdown_normal")

    async def _check_consecutive_losses(self) -> RiskState:
        result = await self.db.execute(
            select(Trade)
            .where(Trade.status == "closed")
            .where(Trade.pnl.isnot(None))
            .order_by(Trade.exit_timestamp.desc())
            .limit(10)
        )
        trades = list(result.scalars().all())

        consecutive = 0
        for t in trades:
            if t.pnl is not None and float(t.pnl) < 0:
                consecutive += 1
            else:
                break

        self._consecutive_losses = consecutive

        if consecutive >= 10:
            self._cooldown_end = datetime.now(timezone.utc) + timedelta(hours=2)
            return RiskState(
                status="STOPPED",
                reason=f"{consecutive}_consecutive_system_losses_exceeds_10",
                cooldown_until=self._cooldown_end,
            )
        elif consecutive >= 5:
            return RiskState(
                status="REDUCED",
                reason=f"{consecutive}_consecutive_losses_approaching_limit",
            )

        return RiskState(status="ACTIVE", reason="consecutive_losses_normal")

    async def _check_slippage_spike(self) -> RiskState:
        if self._baseline_slippage is None:
            result = await self.db.execute(
                select(func.avg(Trade.slippage))
                .where(Trade.slippage.isnot(None))
            )
            avg_slip = result.scalar()
            if avg_slip:
                self._baseline_slippage = float(avg_slip)
            else:
                self._baseline_slippage = 0.001

        result = await self.db.execute(
            select(func.avg(Trade.slippage))
            .where(Trade.slippage.isnot(None))
            .where(Trade.exit_timestamp >= datetime.now(timezone.utc) - timedelta(minutes=30))
        )
        recent_slip = result.scalar()
        if recent_slip is None:
            return RiskState(status="ACTIVE", reason="no_recent_slippage_data")

        recent_slip = float(recent_slip)
        baseline = self._baseline_slippage

        if baseline > 0 and recent_slip > baseline * 3:
            self._cooldown_end = datetime.now(timezone.utc) + timedelta(minutes=30)
            return RiskState(
                status="STOPPED",
                reason=f"slippage_spike_{recent_slip:.6f}_exceeds_3x_baseline_{baseline:.6f}",
                cooldown_until=self._cooldown_end,
            )

        return RiskState(status="ACTIVE", reason="slippage_normal")

    async def _check_liquidity_collapse(self) -> RiskState:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        result = await self.db.execute(
            select(func.count())
            .select_from(MarketEvent)
            .where(MarketEvent.timestamp >= cutoff)
        )
        event_count = result.scalar() or 0

        if event_count < 5:
            self._cooldown_end = datetime.now(timezone.utc) + timedelta(minutes=15)
            return RiskState(
                status="STOPPED",
                reason=f"liquidity_collapse_detected_only_{event_count}_events_in_30min",
                cooldown_until=self._cooldown_end,
            )

        return RiskState(status="ACTIVE", reason="liquidity_normal")

    async def _check_ws_stall(self) -> RiskState:
        ws_config_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        db_event_check = True
        try:
            result = await self.db.execute(
                select(func.count())
                .select_from(MarketEvent)
                .where(MarketEvent.timestamp >= ws_config_cutoff)
            )
            event_count = result.scalar() or 0
            if event_count == 0:
                db_event_check = False
        except Exception:
            db_event_check = False

        ws_stall_timed_out = False
        if self._last_ws_timestamp:
            elapsed = (datetime.now(timezone.utc) - self._last_ws_timestamp).total_seconds()
            if elapsed > settings.WS_STALL_SECONDS:
                ws_stall_timed_out = True

        if not db_event_check or ws_stall_timed_out:
            reason_parts = []
            if not db_event_check:
                reason_parts.append("no_db_events_10min")
            if ws_stall_timed_out:
                elapsed = (datetime.now(timezone.utc) - self._last_ws_timestamp).total_seconds()
                reason_parts.append(f"ws_stalled_{elapsed:.0f}s")
            self._cooldown_end = datetime.now(timezone.utc) + timedelta(minutes=5)
            return RiskState(
                status="STOPPED",
                reason=f"ws_ingestion_stalled:{','.join(reason_parts)}",
                cooldown_until=self._cooldown_end,
            )

        return RiskState(status="ACTIVE", reason="ws_active")

    async def _check_market_data_stability(self) -> RiskState:
        now = datetime.now(timezone.utc)

        if self._last_reconnect_reset < now - timedelta(minutes=10):
            self._reconnect_count_last_10min = 0
            self._last_reconnect_reset = now

        result = await self.db.execute(
            select(func.count())
            .select_from(MarketEvent)
            .where(MarketEvent.timestamp >= now - timedelta(seconds=60))
        )
        events_last_60s = result.scalar() or 0

        if events_last_60s == 0:
            from app.services.pipeline_metrics import inc_trading_halt
            await inc_trading_halt("no_ws_messages_60s")
            return RiskState(
                status="MARKET_DATA_UNSTABLE",
                reason="no_ws_messages_in_60s",
            )

        if self._reconnect_count_last_10min > 5:
            from app.services.pipeline_metrics import inc_trading_halt
            await inc_trading_halt("reconnect_storm")
            return RiskState(
                status="MARKET_DATA_UNSTABLE",
                reason=f"reconnect_storm_{self._reconnect_count_last_10min}_reconnects_in_10min",
            )

        if events_last_60s < 2:
            from app.services.pipeline_metrics import inc_trading_halt
            await inc_trading_halt("event_throughput_collapse")
            return RiskState(
                status="MARKET_DATA_UNSTABLE",
                reason=f"event_throughput_collapse_only_{events_last_60s}_events_in_60s",
            )

        return RiskState(status="ACTIVE", reason="market_data_stable")

    def record_reconnect(self):
        now = datetime.now(timezone.utc)
        if self._last_reconnect_reset < now - timedelta(minutes=10):
            self._reconnect_count_last_10min = 0
            self._last_reconnect_reset = now
        self._reconnect_count_last_10min += 1

    def get_portfolio_drawdown_curve(self) -> list[float]:
        return list(self._portfolio_drawdown_curve)

    def get_state(self) -> RiskState:
        return self._state

    def reset(self):
        self._state = RiskState(status="ACTIVE", reason="reset")
        self._consecutive_losses = 0
        self._cooldown_end = None
